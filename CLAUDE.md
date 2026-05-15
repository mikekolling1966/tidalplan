# TidalPlan — Claude Code Project Context

## What this is
TidalPlan is a self-hosted maritime web app for finding the best tidal departure time
for a sailing passage. Built with FastAPI (Python) backend and vanilla JS / Leaflet frontend.
Deployed on a Raspberry Pi 4 at 192.168.1.30:8081 on the boat's local network.

GitHub: https://github.com/mikekolling1966/tidalplan

## How to deploy a change
```
git add <files>
git commit -m "message"
git push
python scripts/deploy.py   # SSH to Pi, git pull, restart service
```

## Architecture
- **Backend**: FastAPI, port 8081, served by uvicorn via systemd (`tidalplan.service`)
- **Frontend**: Static files in `frontend/` served by FastAPI, Leaflet.js map
- **Pi install path**: `/opt/tidalplan/`
- **Pi venv**: `/opt/tidalplan/venv/`
- **Pi .env**: `/opt/tidalplan/.env` — contains UKHO_API_KEY, CMEMS_USERNAME, CMEMS_PASSWORD

## Data sources (priority order)
1. **CMEMS** (Copernicus Marine) — real 1.5 km hydrodynamic model, 7-day forecast, hourly.
   Downloaded on startup to `data/cmems_current_cache.nc`, refreshed every 12h.
   Coverage: 48°–54.5°N, 5.5°W–8.5°E (English Channel, Thames, North Sea).
   Dataset: `NWSHELF_ANALYSISFORECAST_PHY_004_013`
2. **UKHO Admiralty API** — 608 UK stations, HW/LW events, cosine interpolation for height curve.
   Station list cached to `data/ukho_stations_cache.json`.
3. **TICON-4 harmonic constants** — 13 Channel/NS stations (Calais, Dunkirk, Cherbourg, Ostend etc.)
   Stored in `data/ticon4_channel.json`, computed locally, no API call.
4. **Stream directions fallback** — flood/ebb directions from NP249/250/251/233 atlases,
   ~50 stations in `app/services/stream_directions.py`.

## Key files
```
app/main.py                   FastAPI app + CMEMS startup lifespan
app/config.py                 Loads .env variables
app/services/cmems.py         CMEMS download, cache, get_stream()
app/services/optimizer.py     Departure window scoring engine
app/services/ukho.py          UKHO API client
app/services/harmonics.py     TICON-4 harmonic prediction
app/services/gpx_parser.py    3-tier GPX parser (handles OpenCPN namespaces)
app/services/stream_directions.py  Atlas flood/ebb direction lookup
app/routers/routing.py        POST /api/route/analyse (GPX upload + JSON)
app/routers/tides.py          GET  /api/tides/stations, /cmems/status
frontend/index.html           Single-page app
frontend/app.js               Map, analysis UI, sortable results, resize handle
frontend/style.css            Styles inc. CMEMS badge, drag-to-resize handle
scripts/config.py             SSH + API credentials (obfuscated with base64)
scripts/deploy.py             Deploy to Pi
scripts/install_pi.py         First-time Pi install
scripts/check_cmems.py        Poll CMEMS status until ready
```

## Credentials (see scripts/config.py — base64 encoded)
- Pi SSH: pi @ 192.168.1.30
- UKHO API key: in scripts/config.py
- CMEMS: mike.kolling@dynamics247.net / in scripts/config.py

## API endpoints
- `POST /api/route/analyse`        — GPX file upload → ranked departure windows
- `POST /api/route/analyse-json`   — JSON waypoints → ranked departure windows
- `GET  /api/tides/stations`       — all stations list
- `GET  /api/tides/cmems/status`   — CMEMS forecast window, age, availability
- `POST /api/tides/cmems/refresh`  — trigger manual CMEMS re-download

## Scoring formula
```
weighted_fair = Σ dist × (1 + stream_component / vessel_speed)   [fair legs]
weighted_foul = Σ dist × |stream_component / vessel_speed|        [foul legs]
score = clamp(50 + (weighted_fair - weighted_foul×0.5) / total_dist × 50, 0, 100)
Excellent ≥75, Good ≥50, Fair ≥25, Poor <25
```

## Known quirks / past fixes
- OpenCPN GPX files use `opencpn:` namespace without declaration — handled by
  3-tier parser in gpx_parser.py (sanitise → gpxpy → regex fallback)
- CMEMS download is ~50 MB, takes 2-5 min on Pi — server starts immediately,
  badge shows amber "Station fallback" until it's ready
- `station_name` in LegResult is always the nearest station regardless of whether
  CMEMS or station fallback is used — the `stream_source` field says "cmems" or "station:NAME"
- Cache-busting: static files served with no-cache headers; bump `?v=N` in index.html
  if browser stubbornly caches old JS/CSS

## Future ideas (discussed, not started)
- OpenCPN plugin: C++ plugin using wxWebView to embed TidalPlan UI, reads active
  route via OpenCPN plugin API, posts to Pi JSON endpoint, shows results in docked panel
