"""
Harmonic tidal prediction for non-UK stations using TICON-4 constants.
Covers English Channel, North Sea, French/Belgian/Dutch coasts.

Phase lags (g) are Greenwich phase lags in degrees.
V0 values at 2000-01-01 00:00 UTC from standard astronomical arguments.
"""
import math
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "ticon4_channel.json"
)

# Constituent angular speeds in degrees/hour
SPEEDS: dict[str, float] = {
    "M2":  28.9841042,
    "S2":  30.0000000,
    "N2":  28.4397295,
    "K2":  30.0821373,
    "K1":  15.0410686,
    "O1":  13.9430356,
    "P1":  14.9589314,
    "Q1":  13.3986609,
    "M4":  57.9682084,
    "MS4": 58.9841042,
    "MN4": 57.4238337,
    "M6":  86.9523126,
}

# V0 equilibrium arguments at 2000-01-01 00:00 UTC (degrees, approximate)
V0_J2000: dict[str, float] = {
    "M2":  243.56, "S2":   0.00, "N2":  73.44, "K2":  86.03,
    "K1":  257.30, "O1":  10.04, "P1": 344.55, "Q1": 259.00,
    "M4":  127.12, "MS4": 243.56, "MN4": 317.00, "M6":  10.68,
}

# Reference epoch as Unix timestamp
_T_REF = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()

_stations_cache: Optional[list[dict]] = None


def _load_stations() -> list[dict]:
    global _stations_cache
    if _stations_cache is None:
        with open(_DATA_FILE, "r") as f:
            _stations_cache = json.load(f)
    return _stations_cache


def predict_height(station: dict, t: datetime) -> float:
    """Predict tidal height in metres at time t for a TICON-4 station."""
    T = (t.timestamp() - _T_REF) / 3600.0  # hours from epoch
    h = station["Z0"]
    for c in station["constituents"]:
        name = c["name"]
        if name in SPEEDS:
            sigma = SPEEDS[name]
            V0 = V0_J2000.get(name, 0.0)
            g = c["phase"]
            angle = math.radians(sigma * T + V0 - g)
            h += c["amplitude"] * math.cos(angle)
    return h


def predict_heights(station: dict, times: list[datetime]) -> list[float]:
    return [predict_height(station, t) for t in times]


def height_rate(station: dict, t: datetime, delta_hours: float = 0.25) -> float:
    """Return dh/dt in m/hr (positive = rising, negative = falling)."""
    dt = timedelta(hours=delta_hours)
    h_plus  = predict_height(station, t + dt)
    h_minus = predict_height(station, t - dt)
    return (h_plus - h_minus) / (2 * delta_hours)


def get_all_stations() -> list[dict]:
    return _load_stations()


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def get_stations_near(lat: float, lon: float, radius_km: float = 80.0) -> list[dict]:
    return [
        s for s in _load_stations()
        if _haversine_km(lat, lon, s["lat"], s["lon"]) <= radius_km
    ]


def find_hw_lw(station: dict, start: datetime, end: datetime, step_minutes: int = 10) -> list[dict]:
    """Find HW/LW events by scanning for sign changes in dh/dt."""
    events = []
    t = start
    dt = timedelta(minutes=step_minutes)
    prev_rate = height_rate(station, t)
    while t <= end:
        t += dt
        curr_rate = height_rate(station, t)
        if prev_rate * curr_rate < 0:
            # Sign change: refine by bisection
            ta, tb = t - dt, t
            for _ in range(8):
                tm = ta + (tb - ta) / 2
                rm = height_rate(station, tm)
                if prev_rate * rm < 0:
                    tb = tm
                else:
                    ta = tm
            tm = ta + (tb - ta) / 2
            h = predict_height(station, tm)
            event_type = "HighWater" if curr_rate < 0 else "LowWater"
            events.append({"time": tm, "height": round(h, 2), "event_type": event_type})
        prev_rate = curr_rate
    return events
