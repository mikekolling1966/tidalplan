"""
UKHO Admiralty Tidal API client.
Discovery tier: free, 10,000 req/month, 607 UK stations, 6-day predictions.
Register at: https://admiraltyapi.portal.azure.com/
"""
import math
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from app.config import UKHO_API_KEY, UKHO_BASE_URL
from app.services.stream_directions import enrich_station


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _headers() -> dict:
    return {"Ocp-Apim-Subscription-Key": UKHO_API_KEY}


_stations_cache: list[dict] = []
_stations_fetched: bool = False
_STATION_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ukho_stations_cache.json")

def _load_station_disk_cache() -> list[dict]:
    try:
        with open(_STATION_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def _save_station_disk_cache(stations: list[dict]):
    try:
        with open(_STATION_CACHE_FILE, "w") as f:
            json.dump(stations, f)
    except Exception:
        pass


async def get_all_stations() -> list[dict]:
    """Return all UKHO tidal stations. Memory-cached, then disk-cached, then API."""
    global _stations_cache, _stations_fetched
    if _stations_fetched:
        return _stations_cache
    # Try disk cache first
    disk = _load_station_disk_cache()
    if disk:
        # Re-enrich from disk cache (stream_directions may have been updated
        # since the cache was written, so always apply enrichment on load)
        _stations_cache = [enrich_station(s) for s in disk]
        _stations_fetched = True
        return _stations_cache
    if not UKHO_API_KEY:
        _stations_fetched = True
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{UKHO_BASE_URL}/Stations", headers=_headers())
            r.raise_for_status()
            features = r.json().get("features", [])
            stations = []
            for f in features:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [None, None])
                station = {
                    "id": props.get("Id"),
                    "name": props.get("Name"),
                    "country": props.get("Country", "GB"),
                    "lat": coords[1],
                    "lon": coords[0],
                    "source": "ukho",
                    "continuous_heights_available": props.get("ContinuousHeightsAvailable", False),
                }
                enrich_station(station)
                stations.append(station)
            _stations_cache = stations
            _stations_fetched = True
            _save_station_disk_cache(stations)
            return _stations_cache
    except Exception:
        _stations_fetched = True
        return []


async def get_stations_near(lat: float, lon: float, radius_km: float = 80.0) -> list[dict]:
    """Return UKHO stations within radius_km of the given point."""
    all_st = await get_all_stations()
    return [
        s for s in all_st
        if s["lat"] and s["lon"] and _haversine_km(lat, lon, s["lat"], s["lon"]) <= radius_km
    ]


_events_cache: dict[str, list] = {}


async def get_tidal_events(station_id: str, start: datetime, end: datetime) -> list[dict]:
    """
    Return HW/LW tidal events for a UKHO station.
    Each event: {time, height, event_type ('HighWater'|'LowWater')}
    """
    if not UKHO_API_KEY:
        return []
    cache_key = f"{station_id}_{start.date()}_{end.date()}"
    if cache_key in _events_cache:
        return _events_cache[cache_key]
    params = {
        "StartDateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "EndDateTime":   end.strftime("%Y-%m-%dT%H:%M:%S"),
        "NumberOfRows":  500,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{UKHO_BASE_URL}/Stations/{station_id}/TidalEvents"
        r = await client.get(url, params=params, headers=_headers())
        r.raise_for_status()
        events = []
        for ev in r.json():
            events.append({
                "time": datetime.fromisoformat(ev["DateTime"].rstrip("Z")).replace(tzinfo=timezone.utc),
                "height": float(ev["Height"]),
                "event_type": ev["EventType"],
            })
        result = sorted(events, key=lambda e: e["time"])
        _events_cache[cache_key] = result
        return result


def interpolate_height(events: list[dict], t: datetime) -> Optional[float]:
    """
    Cosine interpolation between HW/LW events.
    Returns height in metres, or None if t is outside the event range.
    """
    if not events:
        return None
    if t <= events[0]["time"]:
        return events[0]["height"]
    if t >= events[-1]["time"]:
        return events[-1]["height"]
    for i in range(len(events) - 1):
        t1, t2 = events[i]["time"], events[i+1]["time"]
        if t1 <= t <= t2:
            h1, h2 = events[i]["height"], events[i+1]["height"]
            span = (t2 - t1).total_seconds()
            elapsed = (t - t1).total_seconds()
            f = elapsed / span
            return h1 + (h2 - h1) * (1 - math.cos(math.pi * f)) / 2
    return None


def height_rate(events: list[dict], t: datetime, delta_hours: float = 0.25) -> float:
    """Return dh/dt in m/hr at time t (finite difference)."""
    dt = timedelta(hours=delta_hours)
    h_plus  = interpolate_height(events, t + dt)
    h_minus = interpolate_height(events, t - dt)
    if h_plus is None or h_minus is None:
        return 0.0
    return (h_plus - h_minus) / (2 * delta_hours)
