"""Wind GRIB data service — parses and caches uploaded GRIB forecast files.

Accepts GRIB1/GRIB2 files from any model (GFS, ECMWF, UKMO, etc.).
Looks for 10 m U/V wind components; falls back to any U/V pair found.
Requires cfgrib + eccodes:
    pip install cfgrib
    apt install libeccodes-dev   # Debian/Raspberry Pi
    brew install eccodes          # macOS
"""
import math
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_ds = None
_summary: dict = {}

_U_NAMES = ["u10", "u", "10u", "UGRD", "ugrd", "uas"]
_V_NAMES = ["v10", "v", "10v", "VGRD", "vgrd", "vas"]


def _find_var(ds, names):
    for name in names:
        if name in ds:
            return name
    return None


def _lat_coord(ds):
    for n in ["latitude", "lat"]:
        if n in ds.coords:
            return n
    return None


def _lon_coord(ds):
    for n in ["longitude", "lon"]:
        if n in ds.coords:
            return n
    return None


def _time_dim(ds):
    # cfgrib often uses "step" as the primary time dimension
    for n in ["valid_time", "time", "step"]:
        if n in ds.dims:
            return n
    # Scalar coordinate — single time step
    for n in ["valid_time", "time"]:
        if n in ds.coords:
            return n
    return None


# ── load ──────────────────────────────────────────────────────────────────────

def load_grib(content: bytes) -> dict:
    """Parse GRIB bytes, cache in memory, return summary dict. Blocking — call via executor."""
    global _ds, _summary

    try:
        import cfgrib  # noqa: F401 — presence check
        import xarray as xr
    except ImportError:
        raise RuntimeError(
            "cfgrib not installed — run: pip install cfgrib\n"
            "Also requires eccodes: apt install libeccodes-dev  or  brew install eccodes"
        )

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as f:
            f.write(content)
            tmp = f.name

        ds = _open_wind_dataset(tmp, xr)
        _ds = ds
        _summary = _build_summary(ds)
        logger.info(f"Wind GRIB loaded: {_summary['steps']} steps  "
                    f"{_summary['time_start']} → {_summary['time_end']}")
        return _summary

    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def _open_wind_dataset(path: str, xr):
    """Try several strategies to open the 10 m wind U/V variables."""
    import cfgrib

    # Strategy 1: iterate all logical datasets in the file
    try:
        for ds in cfgrib.open_datasets(path):
            if _find_var(ds, _U_NAMES) and _find_var(ds, _V_NAMES):
                return ds.load()
    except Exception:
        pass

    # Strategy 2: explicit filters
    for filt in [
        {"typeOfLevel": "heightAboveGround", "level": 10},
        {"shortName": ["10u", "10v"]},
        {},
    ]:
        try:
            ds = xr.open_dataset(path, engine="cfgrib", filter_by_keys=filt)
            if _find_var(ds, _U_NAMES) and _find_var(ds, _V_NAMES):
                return ds.load()
            ds.close()
        except Exception:
            continue

    raise ValueError(
        "No 10 m wind data found in GRIB file. "
        "Expected u10/v10 or UGRD/VGRD at heightAboveGround level 10."
    )


def _build_summary(ds) -> dict:
    import numpy as np

    lat = _lat_coord(ds)
    lon = _lon_coord(ds)
    tname = _time_dim(ds)

    if tname == "step" and "valid_time" in ds.coords:
        import numpy as _np2
        times = _np2.atleast_1d(ds["valid_time"].values)
    elif tname:
        import numpy as _np2
        times = _np2.atleast_1d(ds[tname].values)
    else:
        times = []
    t0 = str(times[0])[:16].replace("T", " ") + " UTC" if len(times) else "—"
    t1 = str(times[-1])[:16].replace("T", " ") + " UTC" if len(times) else "—"

    return {
        "loaded": True,
        "u_var": _find_var(ds, _U_NAMES),
        "v_var": _find_var(ds, _V_NAMES),
        "steps": int(len(times)) if tname else 1,
        "time_start": t0,
        "time_end": t1,
        "lat_range": [
            round(float(ds[lat].values.min()), 1),
            round(float(ds[lat].values.max()), 1),
        ] if lat else [],
        "lon_range": [
            round(float(ds[lon].values.min()), 1),
            round(float(ds[lon].values.max()), 1),
        ] if lon else [],
    }


# ── query ─────────────────────────────────────────────────────────────────────

def get_wind(lat: float, lon: float, t: datetime) -> Optional[Tuple[float, float]]:
    """
    Return (speed_knots, direction_degrees_FROM) or None if unavailable.

    Direction follows meteorological convention: the compass bearing the wind
    is blowing FROM (True North = 0°, clockwise).  So a SW wind = 225°.
    """
    if _ds is None:
        return None

    try:
        import numpy as np

        u_var = _find_var(_ds, _U_NAMES)
        v_var = _find_var(_ds, _V_NAMES)
        if not u_var or not v_var:
            return None

        lat_c  = _lat_coord(_ds)
        lon_c  = _lon_coord(_ds)
        tname  = _time_dim(_ds)

        t_np = np.datetime64(
            t.astimezone(timezone.utc).replace(tzinfo=None), "ns"
        )

        # Nearest grid cell
        sel_kwargs: dict = {}
        if lat_c:
            sel_kwargs[lat_c] = lat
        if lon_c:
            sel_kwargs[lon_c] = lon
        point = _ds.sel(sel_kwargs, method="nearest")

        # Nearest time step -- cfgrib uses "step" dim, "valid_time" as coord
        if tname and tname in point.dims:
            if tname == "step" and "valid_time" in point.coords:
                vt_vals = np.atleast_1d(point["valid_time"].values)
                idx = int(np.argmin(np.abs(vt_vals - t_np)))
                point = point.isel({tname: idx})
            else:
                try:
                    point = point.sel({tname: t_np}, method="nearest")
                except Exception:
                    point = point.isel({tname: 0})

        u = float(np.asarray(point[u_var]).flat[0])   # eastward  m/s
        v = float(np.asarray(point[v_var]).flat[0])   # northward m/s

        if math.isnan(u) or math.isnan(v):
            return None

        # Determine unit conversion: most models use m/s (multiply by 1.944 to get knots)
        # Some commercial GRIBs (e.g. METEOCONSULT) store values already in knots
        u_units = str(_ds[u_var].attrs.get("units", "m s**-1")).lower()
        if "knot" in u_units or u_units in ("kt", "kts", "kn"):
            ms_to_kt = 1.0   # already in knots
        else:
            ms_to_kt = 1.94384  # m/s → knots
        speed_kt = math.sqrt(u ** 2 + v ** 2) * ms_to_kt
        # atan2(-u, -v) gives the direction wind is coming FROM
        direction_from = (math.degrees(math.atan2(-u, -v)) + 360) % 360

        return round(speed_kt, 1), round(direction_from, 1)

    except Exception as e:
        logger.debug(f"GRIB wind lookup ({lat:.3f},{lon:.3f}): {e}")
        return None


# ── helpers ───────────────────────────────────────────────────────────────────

def is_loaded() -> bool:
    return _ds is not None


def clear() -> None:
    global _ds, _summary
    _ds = None
    _summary = {}


def status() -> dict:
    if _ds is None:
        return {"loaded": False}
    return _summary
