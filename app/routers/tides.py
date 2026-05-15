from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone, timedelta
from app.services import ukho, harmonics, cmems

router = APIRouter()


@router.get("/cmems/status")
async def cmems_status():
    """CMEMS current data cache status — available forecast window and data source."""
    return cmems.status()


@router.post("/cmems/refresh")
async def cmems_refresh():
    """Manually trigger a CMEMS forecast download."""
    import asyncio
    asyncio.create_task(cmems.download_forecast())
    return {"message": "CMEMS download started in background"}


@router.get("/stations")
async def list_stations(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    radius_km: float = Query(80.0),
):
    """All tidal stations, optionally filtered by proximity."""
    ticon = harmonics.get_all_stations()
    uk    = await ukho.get_all_stations()
    all_stations = ticon + uk

    if lat is not None and lon is not None:
        from app.services.ukho import _haversine_km
        all_stations = [
            s for s in all_stations
            if _haversine_km(lat, lon, s["lat"], s["lon"]) <= radius_km
        ]
    return all_stations


@router.get("/stations/{station_id}/events")
async def tidal_events(
    station_id: str,
    start: str = Query(..., description="ISO datetime UTC e.g. 2025-06-01T00:00:00"),
    end:   str = Query(..., description="ISO datetime UTC"),
):
    """HW/LW events for a station (UKHO or TICON-4)."""
    try:
        start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO 8601.")

    # Try TICON-4 first
    ticon = harmonics.get_all_stations()
    station = next((s for s in ticon if s["id"] == station_id), None)
    if station:
        events = harmonics.find_hw_lw(station, start_dt, end_dt)
        return [{"time": e["time"].isoformat(), "height": e["height"],
                 "event_type": e["event_type"], "source": "ticon4"} for e in events]

    # Try UKHO
    try:
        events = await ukho.get_tidal_events(station_id, start_dt, end_dt)
        return [{"time": e["time"].isoformat(), "height": e["height"],
                 "event_type": e["event_type"], "source": "ukho"} for e in events]
    except Exception as exc:
        raise HTTPException(502, f"UKHO API error: {exc}")


@router.get("/stations/{station_id}/heights")
async def tidal_heights(
    station_id: str,
    start: str = Query(...),
    end:   str = Query(...),
    interval_minutes: int = Query(10),
):
    """Continuous height predictions at regular intervals."""
    try:
        start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format.")

    ticon = harmonics.get_all_stations()
    station = next((s for s in ticon if s["id"] == station_id), None)

    times = []
    t = start_dt
    while t <= end_dt:
        times.append(t)
        t += timedelta(minutes=interval_minutes)

    if station:
        heights = harmonics.predict_heights(station, times)
        return [{"time": t.isoformat(), "height": round(h, 3)} for t, h in zip(times, heights)]

    # UKHO: fetch events then interpolate
    try:
        events = await ukho.get_tidal_events(
            station_id,
            start_dt - timedelta(hours=6),
            end_dt   + timedelta(hours=6)
        )
        result = []
        for t in times:
            h = ukho.interpolate_height(events, t)
            result.append({"time": t.isoformat(), "height": round(h, 3) if h is not None else None})
        return result
    except Exception as exc:
        raise HTTPException(502, f"UKHO API error: {exc}")
