"""
Copernicus Marine Service (CMEMS) ocean current data.

Product : Atlantic - European North West Shelf - Ocean Physics Analysis & Forecast
Dataset : NWSHELF_ANALYSISFORECAST_PHY_004_013
Variables: uo (eastward), vo (northward) sea water velocity in m/s
Resolution: 1.5 km grid, hourly timesteps, 7-day rolling forecast
Coverage : 46°–65°N, 19°W–13°E  (English Channel, Thames Estuary, North Sea)
Cost    : FREE — register at https://marine.copernicus.eu/

This replaces the station-based dh/dt stream estimation with real hydrodynamic
model output.  Total currents (tidal + surge + wind-driven) are used, which is
actually better for passage planning than tidal-only predictions.

Set CMEMS_USERNAME and CMEMS_PASSWORD in .env to enable.
Falls back gracefully to the station-based estimate if unavailable.
"""

import math
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

from app.config import CMEMS_USERNAME, CMEMS_PASSWORD

logger = logging.getLogger(__name__)

# ── bounding box ──────────────────────────────────────────────────────────────
# Covers: English Channel, Thames Estuary, East Coast to The Wash,
#         Northern France, Belgium, Netherlands
BBOX = {
    "min_lon": -5.5,
    "max_lon":  8.5,
    "min_lat": 48.0,
    "max_lat": 54.5,
}

DATASET_ID  = "cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT1H-i"
CACHE_FILE  = Path(__file__).parent.parent.parent / "data" / "cmems_current_cache.nc"
MAX_AGE_HRS = 12   # refresh twice a day

# ── module-level state ─────────────────────────────────────────────────────────
_ds          = None          # xarray Dataset loaded into memory
_loaded_at: Optional[datetime] = None
_download_lock = None        # asyncio.Lock, created on first use


def _get_lock():
    global _download_lock
    if _download_lock is None:
        _download_lock = asyncio.Lock()
    return _download_lock


# ── disk cache helpers ─────────────────────────────────────────────────────────

def _cache_is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age_hrs = (datetime.now().timestamp() - CACHE_FILE.stat().st_mtime) / 3600
    return age_hrs < MAX_AGE_HRS


def _try_load_cache() -> bool:
    global _ds, _loaded_at
    if not CACHE_FILE.exists():
        return False
    try:
        import xarray as xr
        logger.info("Loading CMEMS current data from disk cache…")
        _ds = xr.open_dataset(str(CACHE_FILE), engine="netcdf4").load()
        _loaded_at = datetime.now()
        t0 = str(_ds.time.values[0])[:16]
        t1 = str(_ds.time.values[-1])[:16]
        logger.info(f"CMEMS loaded: {len(_ds.time)} hourly steps  {t0} → {t1}")
        return True
    except Exception as e:
        logger.warning(f"Could not load CMEMS cache: {e}")
        _ds = None
        return False


# ── download ───────────────────────────────────────────────────────────────────

def _download_sync() -> bool:
    """Blocking download — always called via run_in_executor."""
    global _ds, _loaded_at

    if not CMEMS_USERNAME or not CMEMS_PASSWORD:
        logger.warning("CMEMS credentials not configured (CMEMS_USERNAME / CMEMS_PASSWORD). "
                       "Using station-based stream estimation as fallback.")
        return False

    try:
        import copernicusmarine
        import xarray as xr

        now   = datetime.now(timezone.utc)
        start = now.strftime("%Y-%m-%dT%H:00:00")
        end   = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:00:00")
        tmp   = str(CACHE_FILE) + ".tmp.nc"

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading CMEMS forecast  {start} → {end} …")
        copernicusmarine.subset(
            dataset_id        = DATASET_ID,
            variables         = ["uo", "vo"],
            minimum_longitude = BBOX["min_lon"],
            maximum_longitude = BBOX["max_lon"],
            minimum_latitude  = BBOX["min_lat"],
            maximum_latitude  = BBOX["max_lat"],
            start_datetime    = start,
            end_datetime      = end,
            minimum_depth     = 0.0,
            maximum_depth     = 1.5,    # surface layer only
            output_filename   = tmp,
            force_download    = True,
            username          = CMEMS_USERNAME,
            password          = CMEMS_PASSWORD,
        )

        Path(tmp).replace(CACHE_FILE)   # atomic replace

        _ds = xr.open_dataset(str(CACHE_FILE), engine="netcdf4").load()
        _loaded_at = datetime.now()
        size_mb = CACHE_FILE.stat().st_size / 1_048_576
        logger.info(f"CMEMS download complete: {len(_ds.time)} steps, {size_mb:.1f} MB")
        return True

    except ImportError:
        logger.error("copernicusmarine package not installed — run: pip install copernicusmarine")
        return False
    except Exception as e:
        logger.error(f"CMEMS download failed: {e}")
        return False


async def download_forecast() -> bool:
    """Download a fresh CMEMS forecast without blocking the async event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync)


async def ensure_ready() -> bool:
    """
    Ensure current data is in memory.  Call at startup and before analysis.
    Thread-safe via asyncio.Lock so parallel requests don't trigger double-download.
    """
    global _ds, _loaded_at

    # Already loaded and fresh?
    if _ds is not None and _loaded_at:
        if (datetime.now() - _loaded_at).total_seconds() / 3600 < MAX_AGE_HRS:
            return True

    async with _get_lock():
        # Re-check after acquiring lock (another coroutine may have downloaded meanwhile)
        if _ds is not None and _loaded_at:
            if (datetime.now() - _loaded_at).total_seconds() / 3600 < MAX_AGE_HRS:
                return True

        # Fresh disk cache?
        if _cache_is_fresh() and _try_load_cache():
            return True

        # Download
        return await download_forecast()


async def refresh_loop():
    """Background task: refresh CMEMS data every MAX_AGE_HRS hours."""
    while True:
        await asyncio.sleep(MAX_AGE_HRS * 3600)
        logger.info("Scheduled CMEMS refresh starting…")
        await download_forecast()


# ── query ──────────────────────────────────────────────────────────────────────

def get_stream(lat: float, lon: float, t: datetime) -> Optional[Tuple[float, float]]:
    """
    Return (speed_knots, direction_degrees_true) of the ocean current at
    position (lat, lon) and time t.

    Returns None if:
      - CMEMS data is not loaded
      - Position is over land (fill value in model)
      - Time is outside the cached forecast window

    Direction is the bearing the water flows TOWARD (True North = 0°).
    Uses atan2(u, v) where u = eastward, v = northward component.
    """
    if _ds is None:
        return None

    try:
        import numpy as np

        # Clamp request to cache window
        t_first = _ds.time.values[0]
        t_last  = _ds.time.values[-1]
        t_naive = t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t
        t_np    = np.datetime64(t_naive, "ns")

        if t_np < t_first or t_np > t_last:
            return None   # outside forecast window

        # Nearest-neighbour in space and time
        point = _ds.sel(
            longitude = lon,
            latitude  = lat,
            time      = t_np,
            method    = "nearest",
        )

        u = float(point["uo"].values)   # eastward  m/s
        v = float(point["vo"].values)   # northward m/s

        if math.isnan(u) or math.isnan(v):
            return None   # land / fill value

        speed_knots = math.sqrt(u**2 + v**2) * 1.94384
        # atan2(u, v) → angle east of north → same as true bearing clockwise from north
        direction   = (math.degrees(math.atan2(u, v)) + 360) % 360

        return round(speed_knots, 2), round(direction, 1)

    except Exception as e:
        logger.debug(f"CMEMS get_stream({lat:.3f},{lon:.3f}) error: {e}")
        return None


def status() -> dict:
    """Summary dict for the status API endpoint."""
    if _ds is None:
        creds_set = bool(CMEMS_USERNAME and CMEMS_PASSWORD)
        return {
            "available": False,
            "reason": "No data loaded" if creds_set else "Credentials not configured",
            "credentials_set": creds_set,
        }
    t0      = str(_ds.time.values[0])[:16].replace("T", " ") + " UTC"
    t1      = str(_ds.time.values[-1])[:16].replace("T", " ") + " UTC"
    age_hrs = round((datetime.now() - _loaded_at).total_seconds() / 3600, 1) if _loaded_at else None
    return {
        "available"  : True,
        "forecast_from": t0,
        "forecast_to"  : t1,
        "steps"      : int(len(_ds.time)),
        "age_hours"  : age_hrs,
        "bbox"       : BBOX,
        "source"     : "CMEMS NWSHELF_ANALYSISFORECAST_PHY_004_013 @ 1.5 km",
    }
