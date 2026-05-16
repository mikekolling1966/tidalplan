from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from datetime import datetime, timezone
from typing import Optional
import json

from app.services.gpx_parser import parse_gpx
from app.services.optimizer import analyse_route

router = APIRouter()


@router.post("/analyse")
async def analyse(
    gpx_file: UploadFile = File(...),
    vessel_speed: float = Form(7.0),
    start_datetime: str = Form(...),
    end_datetime:   str = Form(...),
    interval_minutes: int = Form(30),
    top_n: int = Form(20),
):
    """
    Upload a GPX route and get ranked departure windows.

    - vessel_speed: knots through water
    - start_datetime / end_datetime: ISO 8601 UTC, the range of departure times to test
    - interval_minutes: how often to test a departure (30 = every half hour)
    - top_n: return this many best windows
    """
    content = await gpx_file.read()
    try:
        route = parse_gpx(content)
    except Exception as exc:
        raise HTTPException(400, f"GPX parse error: {exc}")

    try:
        start_dt = datetime.fromisoformat(start_datetime).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(end_datetime).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO 8601 e.g. 2025-06-10T06:00:00")

    if (end_dt - start_dt).total_seconds() < 3600:
        raise HTTPException(400, "Search window must be at least 1 hour.")

    if len(route) < 2:
        raise HTTPException(400, "Route needs at least 2 waypoints.")

    waypoints = [(wp.lat, wp.lon) for wp in route.waypoints]

    windows, warnings = await analyse_route(
        waypoints=waypoints,
        vessel_speed_knots=vessel_speed,
        start_dt=start_dt,
        end_dt=end_dt,
        interval_minutes=interval_minutes,
        top_n=top_n,
    )

    return {
        "route_name": route.name,
        "waypoint_count": len(waypoints),
        "windows_tested": int((end_dt - start_dt).total_seconds() / 60 / interval_minutes) + 1,
        "warnings": warnings,
        "results": [
            {
                "rank": i + 1,
                "departure": w.departure_time.isoformat(),
                "eta": w.eta.isoformat(),
                "passage_hours": w.passage_hours,
                "score": w.score,
                "score_label": w.score_label,
                "legs": [
                    {
                        "leg": l.leg_index + 1,
                        "distance_nm": l.distance_nm,
                        "heading": l.heading,
                        "duration_hours": l.duration_hours,
                        "stream_speed_kt": l.stream_speed,
                        "stream_dir": l.stream_direction,
                        "stream_component_kt": l.stream_component,
                        "station": l.station_name,
                        "source": l.stream_source,
                        "wind_speed_kt": l.wind_speed_kt,
                        "wind_direction": l.wind_direction,
                    }
                    for l in w.legs
                ],
                "notes": w.notes,
            }
            for i, w in enumerate(windows)
        ],
    }


@router.post("/analyse-json")
async def analyse_json(body: dict):
    """
    Same as /analyse but accepts JSON body with waypoints list.
    Body: {waypoints: [[lat,lon],...], vessel_speed, start_datetime, end_datetime,
           interval_minutes?, top_n?}
    """
    try:
        waypoints = [tuple(wp) for wp in body["waypoints"]]
        vessel_speed = float(body.get("vessel_speed", 7.0))
        start_dt = datetime.fromisoformat(body["start_datetime"]).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(body["end_datetime"]).replace(tzinfo=timezone.utc)
        interval_minutes = int(body.get("interval_minutes", 30))
        top_n = int(body.get("top_n", 20))
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))

    if len(waypoints) < 2:
        raise HTTPException(400, "Need at least 2 waypoints.")

    windows, warnings = await analyse_route(waypoints, vessel_speed, start_dt, end_dt, interval_minutes, top_n)

    return {
        "waypoint_count": len(waypoints),
        "windows_tested": int((end_dt - start_dt).total_seconds() / 60 / interval_minutes) + 1,
        "warnings": warnings,
        "results": [
            {
                "rank": i + 1,
                "departure": w.departure_time.isoformat(),
                "eta": w.eta.isoformat(),
                "passage_hours": w.passage_hours,
                "score": w.score,
                "score_label": w.score_label,
                "legs": [
                    {
                        "leg": l.leg_index + 1,
                        "distance_nm": l.distance_nm,
                        "heading": l.heading,
                        "duration_hours": l.duration_hours,
                        "stream_speed_kt": l.stream_speed,
                        "stream_dir": l.stream_direction,
                        "stream_component_kt": l.stream_component,
                        "station": l.station_name,
                        "source": l.stream_source,
                        "wind_speed_kt": l.wind_speed_kt,
                        "wind_direction": l.wind_direction,
                    }
                    for l in w.legs
                ],
            }
            for i, w in enumerate(windows)
        ],
    }
