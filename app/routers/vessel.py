from fastapi import APIRouter
from app.services import signalk

router = APIRouter()


@router.get("/position")
async def vessel_position():
    """Current vessel position from Signal K. Returns null values if unavailable."""
    pos = await signalk.get_position()
    return pos or {"lat": None, "lon": None}


@router.get("/data")
async def vessel_data():
    """Combined vessel data: position, speed, heading."""
    pos = await signalk.get_position()
    spd = await signalk.get_speed_knots()
    hdg = await signalk.get_heading()
    return {
        "position": pos,
        "speed_knots": spd,
        "heading": hdg,
    }
