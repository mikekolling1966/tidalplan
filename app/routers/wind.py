import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services import grib_wind

router = APIRouter()


@router.post("/upload")
async def upload_wind_grib(grib_file: UploadFile = File(...)):
    """Upload a wind GRIB file. Stored in memory for use in subsequent route analysis."""
    content = await grib_file.read()
    loop = asyncio.get_event_loop()
    try:
        meta = await loop.run_in_executor(None, grib_wind.load_grib, content)
    except RuntimeError as exc:
        raise HTTPException(501, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"GRIB parse error: {exc}")

    return {"filename": grib_file.filename, **meta}


@router.get("/status")
async def wind_status():
    return grib_wind.status()


@router.delete("/clear")
async def clear_wind():
    grib_wind.clear()
    return {"cleared": True}
