# TidalPlan

A self-hosted web app for sailors that finds the best departure time for a tidal passage. Load your GPX route, set a search window, and TidalPlan tests every departure slot — ranking them by how much of the passage benefits from a fair tide.

Designed to run on a Raspberry Pi alongside Signal K and be accessible from any device on the boat's network.

---

## Screenshot

![TidalPlan UI showing the map, sidebar controls, and ranked results table](docs/screenshot.png)

---

## Features

| | |
|---|---|
| 🗺️ **GPX import** | Load routes from OpenCPN, Navionics, iNavX, etc. Handles OpenCPN's non-standard namespace extensions |
| ✏️ **Draw a route** | Click waypoints directly on the map |
| ⚓ **Departure optimiser** | Tests every 15/30/60-minute slot across your chosen date range and ranks the results |
| 📡 **Real ocean currents** | Uses Copernicus Marine (CMEMS) hydrodynamic model: 1.5 km grid, hourly, 7-day forecast. Total currents (tidal + surge + wind-driven) |
| 📍 **Station fallback** | If CMEMS is unavailable, falls back to 600+ UK UKHO Admiralty stations + 13 Channel/North Sea TICON-4 stations |
| 🌊 **Tidal curve viewer** | Click any station on the map to plot its predicted tidal curve |
| 🏅 **Scoring & rating** | Each departure scored 0–100 (Excellent / Good / Fair / Poor) |
| 📊 **Sortable table** | Sort by duration, departure time, ETA or tidal score |
| 📥 **CSV export** | Download the full results table |
| 🟢 **Live data source badge** | Sidebar shows whether CMEMS model data or station fallback is active |
| 📐 **Resizable results panel** | Drag the grip bar to make the results table as tall as you need |

---

## How It Works

### Step 1 — Tidal height prediction

**UK stations (UKHO Admiralty API)**  
The free UKHO Discovery API provides High Water and Low Water times and heights for 608 UK ports, 6 days ahead. TidalPlan fetches these events and reconstructs the full tidal curve using a cosine interpolation between HW/LW pairs — the standard Admiralty *rule of twelfths* approach in continuous form.

**Channel & North Sea stations (TICON-4 harmonic constants)**  
For 13 French, Dutch and Belgian ports the tidal height is predicted directly from harmonic constituents stored locally (no API call needed):

```
h(t) = Z0 + Σ Hᵢ × cos(σᵢ·t + V0ᵢ − gᵢ)
```

where `σᵢ` is the constituent speed (°/hr), `V0ᵢ` is the astronomical argument at J2000.0, and `gᵢ` is the station's phase lag. Constituents used: M2, S2, N2, K2, K1, O1, P1, Q1, Mf, Mm, SSA.

---

### Step 2 — Tidal stream (current) data

**Primary: CMEMS hydrodynamic model**  
[Copernicus Marine Service](https://marine.copernicus.eu/) provides a free 7-day rolling ocean forecast for the Northwest European Shelf at 1.5 km resolution, updated twice daily. TidalPlan downloads this on startup as a NetCDF file (≈ 50 MB) and caches it locally, refreshing every 12 hours.

Product: `NWSHELF_ANALYSISFORECAST_PHY_004_013`  
Dataset: `cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT1H-i`  
Variables: `uo` (eastward m/s), `vo` (northward m/s)  
Coverage: 48°–54.5°N, 5.5°W–8.5°E (English Channel, Thames Estuary, North Sea, Dutch/Belgian coast)

For each leg midpoint at the time the vessel is estimated to be there:
```
speed_knots = √(u² + v²) × 1.94384
direction   = (atan2(u, v) × 180/π + 360) % 360   # bearing the water flows toward
```

This is better than tidal-only predictions because it includes meteorological surge and wind-driven currents.

**Fallback: station-based stream estimation**  
If CMEMS credentials are not configured or the download has not yet completed, stream speed is estimated from the rate of change of tidal height using the Admiralty K-factor method:

```
K = (T_M2 × spring_max_speed) / (π × spring_tidal_range)

stream_speed = K × |dh/dt|
```

Direction comes from a lookup table of flood and ebb directions sourced from Admiralty Tidal Stream Atlases **NP249** (Thames Estuary), **NP250** (English Channel Eastern), **NP251** (North Sea Southern) and **NP233** (Dover Strait), covering 50+ stations from the Thames to The Wash and across to the near Continent.

---

### Step 3 — Route optimisation

For each candidate departure time, the engine walks leg by leg:

1. Calculates the great-circle distance and true heading for each leg
2. Looks up the current vector at the leg midpoint and the time the vessel is estimated to arrive there
3. Projects the current onto the course: `component = speed × cos(angle_between_course_and_current)`
4. Adjusts the effective boat speed: `eff_speed = vessel_speed + component`  (fair tide adds speed; foul tide reduces it)
5. Accumulates elapsed time to give a realistic ETA at each waypoint

**Scoring formula:**
```
weighted_fair = Σ (distance × (1 + component / vessel_speed))   for fair-tide legs
weighted_foul = Σ (distance × |component / vessel_speed|)        for foul-tide legs

raw = (weighted_fair − weighted_foul × 0.5) / total_distance
score = clamp(50 + raw × 50, 0, 100)
```

| Score | Rating |
|---|---|
| ≥ 75 | ⭐ Excellent |
| 50–74 | 🟢 Good |
| 25–49 | 🟡 Fair |
| < 25 | 🔴 Poor |

---

## Data Sources

| Source | Coverage | Cost | Notes |
|---|---|---|---|
| UKHO Admiralty API (Discovery) | 608 UK ports | Free | 10,000 req/month; events cached to disk |
| TICON-4 harmonic constants | 13 Channel/NS ports | Free (open data, CC BY 4.0) | Computed locally, no API needed |
| CMEMS NW Shelf forecast | English Channel, North Sea, Thames Estuary | Free | Requires free account at marine.copernicus.eu |

### TICON-4 stations included

| Station | Country | Station | Country |
|---|---|---|---|
| Cherbourg | France | Vlissingen | Netherlands |
| Calais | France | Hoek van Holland | Netherlands |
| Dunkirk | France | Den Helder | Netherlands |
| Dieppe | France | IJmuiden | Netherlands |
| Le Havre | France | Zeebrugge | Belgium |
| Brest | France | Ostend | Belgium |
| Saint-Malo | France | | |

---

## Installation

### Requirements

- Python 3.10 +
- A free UKHO Admiralty API key — register at [admiraltyapi.portal.azure.com](https://admiraltyapi.portal.azure.com/) (Discovery tier, free)
- *(Optional)* A free Copernicus Marine account for CMEMS real current data — register at [marine.copernicus.eu](https://marine.copernicus.eu/)

---

### Raspberry Pi / Linux (recommended)

SSH in and run the one-line installer:

```bash
curl -sSL https://raw.githubusercontent.com/mikekolling1966/tidalplan/master/install.sh | sudo bash
```

This will:
1. Clone the repo to `/opt/tidalplan`
2. Create a Python virtual environment and install all dependencies
3. Ask for your UKHO API key and write `/opt/tidalplan/.env`
4. Install and enable a `systemd` service that starts on boot

TidalPlan will be available at **`http://<pi-ip>:8081`** from any device on the boat network.

**To add CMEMS credentials** (enables real ocean current data):

```bash
echo 'CMEMS_USERNAME=your@email.com' >> /opt/tidalplan/.env
echo 'CMEMS_PASSWORD=yourpassword'   >> /opt/tidalplan/.env
sudo systemctl restart tidalplan
```

The CMEMS download (~50 MB) starts in the background. Check progress:

```bash
sudo journalctl -u tidalplan -f
# or check the status endpoint:
curl http://localhost:8081/api/tides/cmems/status
```

**Useful commands:**

```bash
sudo systemctl status tidalplan       # service status
sudo systemctl restart tidalplan      # restart after config change
sudo journalctl -u tidalplan -f       # live logs
git -C /opt/tidalplan pull            # update to latest version
```

---

### Quick start (any platform)

```bash
git clone https://github.com/mikekolling1966/tidalplan.git
cd tidalplan
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add UKHO_API_KEY and optionally CMEMS_USERNAME / CMEMS_PASSWORD
python start.py
```

Open **http://localhost:8081**.

---

### Docker

```bash
cp .env.example .env     # add your keys
docker compose up -d
```

---

## Configuration

Edit `/opt/tidalplan/.env` (or `.env` in the project root):

```dotenv
# Required — UKHO Admiralty Discovery API
UKHO_API_KEY=your_key_here

# Optional — Copernicus Marine / CMEMS
# Enables real 1.5 km hydrodynamic ocean current data (7-day forecast)
# Free account at https://marine.copernicus.eu/
CMEMS_USERNAME=your@email.com
CMEMS_PASSWORD=yourpassword
```

| Variable | Required | Description |
|---|---|---|
| `UKHO_API_KEY` | Yes | UKHO Admiralty Discovery API key |
| `CMEMS_USERNAME` | No | Copernicus Marine username — enables real current data |
| `CMEMS_PASSWORD` | No | Copernicus Marine password |

Without CMEMS credentials the app still works fully using the station-based stream estimation fallback.

---

## API Endpoints

The FastAPI backend exposes these endpoints (auto-documented at `/docs`):

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/route/analyse` | Analyse a GPX file upload — returns ranked departure windows |
| `POST` | `/api/route/analyse-json` | Same but accepts JSON body with `[[lat,lon],...]` waypoints |
| `GET` | `/api/tides/stations` | List all tidal stations (UKHO + TICON-4) |
| `GET` | `/api/tides/stations/{id}/heights` | Predicted tidal heights at a station |
| `GET` | `/api/tides/cmems/status` | CMEMS data status — forecast window, age, bounding box |
| `POST` | `/api/tides/cmems/refresh` | Trigger a manual CMEMS re-download |
| `GET` | `/api/vessel/position` | Signal K vessel position (if available) |

---

## Project Structure

```
tidalplan/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, static file serving
│   ├── config.py                # Environment variable loading
│   ├── routers/
│   │   ├── tides.py             # /api/tides/* — stations, heights, CMEMS status
│   │   ├── routing.py           # /api/route/* — departure window analysis
│   │   └── vessel.py            # /api/vessel/* — Signal K position stub
│   └── services/
│       ├── cmems.py             # Copernicus Marine download, cache, and current lookup
│       ├── ukho.py              # UKHO Admiralty API client + disk cache
│       ├── harmonics.py         # TICON-4 tidal harmonic prediction engine
│       ├── gpx_parser.py        # Robust GPX parser (handles OpenCPN namespaces)
│       ├── optimizer.py         # Departure window scoring and ranking engine
│       └── stream_directions.py # Flood/ebb directions from NP249/250/251/233 atlases
├── data/
│   ├── ticon4_channel.json      # TICON-4 harmonic constants for 13 Channel/NS stations
│   └── ukho_stations_cache.json # UKHO station list (auto-generated, git-ignored)
├── frontend/
│   ├── index.html               # Single-page app shell
│   ├── app.js                   # Leaflet map, UI logic, results table, resize handle
│   └── style.css                # Responsive styles, CMEMS badge, drag-handle
├── start.py                     # Launch script (python start.py)
├── install.sh                   # One-line Raspberry Pi / Linux installer
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example                 # Template — copy to .env and fill in keys
```

---

## Updating

```bash
# On Raspberry Pi
git -C /opt/tidalplan pull
sudo systemctl restart tidalplan
```

---

## CMEMS data — what to expect

- **First run:** the background download takes 2–5 minutes on a Pi (≈ 50 MB over a typical home broadband connection)
- **While downloading:** the app works immediately using the station-based fallback — the sidebar badge shows amber *"Station fallback"*
- **Once ready:** the badge turns green *"CMEMS model active"* and shows the forecast window
- **Auto-refresh:** the data is refreshed every 12 hours in the background without any restart needed
- **If CMEMS goes down:** automatically falls back to station-based estimation — no error shown to the user

---

## Licence

MIT — free to use, modify and distribute.

---

## Credits

Built by Mike Kolling.

- Tidal harmonic constants from [TICON-4](https://www.bodc.ac.uk/data/published_data_library/catalogue/10.5285/b7bfc082-e849-11e8-b9a3-00163e251233/) © BODC / NOC, CC BY 4.0
- Tidal stream directions from Admiralty Tidal Stream Atlases NP249, NP250, NP251, NP233 © Crown Copyright / UKHO
- Ocean current forecast data from [Copernicus Marine Service](https://marine.copernicus.eu/) (CMEMS), product `NWSHELF_ANALYSISFORECAST_PHY_004_013`, free for registered users
- UK tidal event predictions from [UKHO Admiralty API](https://admiraltyapi.portal.azure.com/) Discovery tier, free up to 10,000 requests/month
- Maps © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors
