"""Fetch live vessel data from a Signal K server."""
import httpx
from typing import Optional
from app.config import SIGNALK_HOST, SIGNALK_PORT

_BASE = f"http://{SIGNALK_HOST}:{SIGNALK_PORT}/signalk/v1/api/vessels/self"


async def get_position() -> Optional[dict]:
    """Return {'lat': float, 'lon': float} or None."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{_BASE}/navigation/position")
            r.raise_for_status()
            v = r.json().get("value", {})
            return {"lat": v["latitude"], "lon": v["longitude"]}
    except Exception:
        return None


async def get_speed_knots() -> Optional[float]:
    """Return speed over ground in knots, or None."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{_BASE}/navigation/speedOverGround")
            r.raise_for_status()
            sog_ms = r.json().get("value")
            if sog_ms is not None:
                return round(sog_ms * 1.94384, 2)  # m/s to knots
    except Exception:
        pass
    return None


async def get_heading() -> Optional[float]:
    """Return true heading in degrees, or None."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{_BASE}/navigation/headingTrue")
            r.raise_for_status()
            hdg_rad = r.json().get("value")
            if hdg_rad is not None:
                import math
                return round(math.degrees(hdg_rad) % 360, 1)
    except Exception:
        pass
    return None
