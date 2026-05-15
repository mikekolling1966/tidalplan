"""
Tidal departure window optimizer.

For each candidate departure time, walks the route at the given vessel speed,
estimating the tidal stream at each leg from the nearest tidal station.
Returns ranked departure windows.
"""
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

from app.services import harmonics, ukho


# ── geometry helpers ──────────────────────────────────────────────────────────

def _haversine_nm(lat1, lon1, lat2, lon2) -> float:
    R_NM = 3440.065
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R_NM * 2 * math.asin(math.sqrt(a))


def _bearing(lat1, lon1, lat2, lon2) -> float:
    """True bearing in degrees from point 1 to point 2."""
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ── station resolution ────────────────────────────────────────────────────────

def _find_nearest_station(lat: float, lon: float, all_stations: list[dict]) -> Optional[dict]:
    if not all_stations:
        return None
    return min(all_stations, key=lambda s: _haversine_km(lat, lon, s["lat"], s["lon"]))


def _station_height_rate(station: dict, t: datetime, ukho_events_cache: dict) -> float:
    """Return dh/dt in m/hr for a station at time t."""
    sid = station.get("id", "")
    if station.get("source") == "ukho":
        events = ukho_events_cache.get(sid, [])
        return ukho.height_rate(events, t)
    else:
        return harmonics.height_rate(station, t)


def _stream_vector_station(station: dict, t: datetime, ukho_events_cache: dict) -> tuple[float, float]:
    """
    Station-based fallback: estimate stream from dh/dt using the Admiralty K-factor
    method, with flood/ebb direction from the station metadata or atlas lookup table.
    """
    rate = _station_height_rate(station, t, ukho_events_cache)

    spring_range  = station.get("spring_range_m", 4.0)
    max_spring_kt = station.get("spring_max_knots", 1.5)
    T_M2 = 12.42  # hours

    if spring_range > 0:
        K = (T_M2 * max_spring_kt) / (math.pi * spring_range)
    else:
        K = 0.5

    speed = min(abs(rate) * K, max_spring_kt * 1.1)

    if rate > 0:
        direction = station.get("flood_direction", 0.0)
    else:
        direction = station.get("ebb_direction", 180.0)

    return speed, direction


def _stream_vector(lat: float, lon: float, station: Optional[dict],
                   t: datetime, ukho_events_cache: dict) -> tuple[float, float, str]:
    """
    Return (speed_knots, direction_degrees_true, source) of ocean current.

    Priority:
      1. CMEMS hydrodynamic model — real u/v at the exact leg midpoint (1.5 km grid,
         hourly, total current = tidal + surge + wind-driven).
      2. Station-based fallback — dh/dt K-factor + atlas flood/ebb direction.

    source is 'cmems' or 'station:<name>'.
    """
    # ── 1. Try CMEMS ──────────────────────────────────────────────────────
    try:
        from app.services import cmems
        result = cmems.get_stream(lat, lon, t)
        if result is not None:
            return result[0], result[1], "cmems"
    except Exception:
        pass

    # ── 2. Station-based fallback ─────────────────────────────────────────
    if station:
        sp, sd = _stream_vector_station(station, t, ukho_events_cache)
        return sp, sd, f"station:{station.get('name', '?')}"

    return 0.0, 0.0, "none"


# ── core walk ────────────────────────────────────────────────────────────────

@dataclass
class LegResult:
    leg_index: int
    distance_nm: float
    heading: float
    duration_hours: float
    stream_speed: float
    stream_direction: float
    stream_component: float  # + = fair, - = foul
    station_name: str
    stream_source: str = "unknown"  # "cmems" or "station:<name>"


@dataclass
class DepartureWindow:
    departure_time: datetime
    eta: datetime
    passage_hours: float
    score: float            # 0–100, higher = more favourable
    score_label: str        # "Excellent" / "Good" / "Fair" / "Poor"
    legs: list[LegResult] = field(default_factory=list)
    notes: str = ""


def _score_label(score: float) -> str:
    if score >= 75:
        return "Excellent"
    if score >= 50:
        return "Good"
    if score >= 25:
        return "Fair"
    return "Poor"


async def analyse_route(
    waypoints: list[tuple[float, float]],
    vessel_speed_knots: float,
    start_dt: datetime,
    end_dt: datetime,
    interval_minutes: int = 30,
    top_n: int = 20,
) -> list[DepartureWindow]:
    """
    Test departure windows every interval_minutes between start_dt and end_dt.
    Returns top_n windows ranked by score (best first).
    """
    if len(waypoints) < 2:
        raise ValueError("Need at least 2 waypoints.")
    if vessel_speed_knots <= 0:
        raise ValueError("Vessel speed must be positive.")

    # Compute leg midpoints for station lookup
    leg_mids = []
    for i in range(len(waypoints) - 1):
        mlat = (waypoints[i][0] + waypoints[i+1][0]) / 2
        mlon = (waypoints[i][1] + waypoints[i+1][1]) / 2
        leg_mids.append((mlat, mlon))

    # Load all stations once
    ticon_stations = harmonics.get_all_stations()
    ukho_stations  = await ukho.get_all_stations()
    all_stations   = ticon_stations + ukho_stations

    # Find nearest station per leg
    leg_stations = [_find_nearest_station(lat, lon, all_stations) for lat, lon in leg_mids]

    # Pre-fetch UKHO events for all unique UKHO stations needed (extended window)
    fetch_start = start_dt - timedelta(hours=6)
    fetch_end   = end_dt + timedelta(hours=36)
    ukho_events_cache: dict[str, list] = {}
    unique_ukho = {s["id"] for s in leg_stations if s and s.get("source") == "ukho"}

    async def _fetch(sid):
        try:
            return sid, await ukho.get_tidal_events(sid, fetch_start, fetch_end)
        except Exception:
            return sid, []

    import asyncio as _asyncio
    results = await _asyncio.gather(*[_fetch(sid) for sid in unique_ukho])
    for sid, events in results:
        ukho_events_cache[sid] = events

    # Iterate departure windows
    results: list[DepartureWindow] = []
    t_dep = start_dt
    dt_step = timedelta(minutes=interval_minutes)

    while t_dep <= end_dt:
        legs: list[LegResult] = []
        current_time = t_dep
        total_fair_nm = 0.0
        total_foul_nm = 0.0
        total_distance = 0.0

        for i, (wp_from, wp_to) in enumerate(zip(waypoints[:-1], waypoints[1:])):
            dist_nm = _haversine_nm(wp_from[0], wp_from[1], wp_to[0], wp_to[1])
            hdg = _bearing(wp_from[0], wp_from[1], wp_to[0], wp_to[1])
            station = leg_stations[i]

            mlat, mlon = leg_mids[i]
            sp, sd, ssrc = _stream_vector(mlat, mlon, station, current_time, ukho_events_cache)
            angle_diff = abs(hdg - sd) % 360
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            component = sp * math.cos(math.radians(angle_diff))
            sname = station.get("name", "?") if station else "none"

            eff_speed = max(vessel_speed_knots + component, 0.3)
            leg_hours = dist_nm / eff_speed
            current_time += timedelta(hours=leg_hours)

            legs.append(LegResult(
                leg_index=i,
                distance_nm=round(dist_nm, 2),
                heading=round(hdg, 1),
                duration_hours=round(leg_hours, 3),
                stream_speed=round(sp, 2),
                stream_direction=round(sd, 1),
                stream_component=round(component, 2),
                station_name=sname,
                stream_source=ssrc,
            ))

            if component >= 0:
                total_fair_nm += dist_nm
            else:
                total_foul_nm += dist_nm
            total_distance += dist_nm

        passage_hours = (current_time - t_dep).total_seconds() / 3600.0

        # Score: fraction of distance with fair tide, weighted by stream strength
        weighted_fair = sum(
            l.distance_nm * (1 + l.stream_component / max(vessel_speed_knots, 1))
            for l in legs if l.stream_component >= 0
        )
        weighted_foul = sum(
            l.distance_nm * abs(l.stream_component / max(vessel_speed_knots, 1))
            for l in legs if l.stream_component < 0
        )
        if total_distance > 0:
            raw_score = (weighted_fair - weighted_foul * 0.5) / total_distance
            score = max(0.0, min(100.0, 50.0 + raw_score * 50.0))
        else:
            score = 50.0

        results.append(DepartureWindow(
            departure_time=t_dep,
            eta=current_time,
            passage_hours=round(passage_hours, 2),
            score=round(score, 1),
            score_label=_score_label(score),
            legs=legs,
        ))
        t_dep += dt_step

    results.sort(key=lambda w: w.score, reverse=True)
    return results[:top_n]
