# TidalPlan

A self-hosted web application for sailors that finds the best departure time for a passage based on tidal conditions. Load your GPX route, set a departure window, and TidalPlan ranks every possible departure slot by how much of the passage will be sailed on a fair tide.

![TidalPlan screenshot](docs/screenshot.png)

---

## Features

- **GPX route import** — load any route exported from OpenCPN, Navionics, or similar
- **Draw a route** — click waypoints directly on the map if you don't have a GPX file
- **Departure window optimiser** — tests every 15/30/60-minute slot across your chosen date range
- **Tidal scoring** — each departure is scored 0–100 based on fair vs foul tidal stream along each leg
- **Sortable results** — sort by duration, departure time, ETA, or tidal score
- **Tidal curve viewer** — click any station on the map to see its predicted tidal curve
- **UK + Cross-Channel coverage** — 600+ UK stations via the UKHO Admiralty API, plus 13 Channel/North Sea stations (Cherbourg, Calais, Dunkirk, Dieppe, Le Havre, Brest, Vlissingen, Hoek van Holland and more) via TICON-4 harmonic constants
- **Runs on a Raspberry Pi** — designed to run on a Signal K server and be accessible from any device on the boat network

---

## How It Works

### Tidal Data Sources

**UKHO Admiralty API (UK stations)**  
Fetches High Water / Low Water times and heights from the UK Hydrographic Office's free Discovery tier (608 stations, 6-day predictions). A cosine interpolation reconstructs the full tidal curve between HW/LW events.

**TICON-4 Harmonic Constants (Channel & North Sea)**  
For French, Dutch and Belgian stations, tidal heights are predicted from harmonic constituents (M2, S2, N2, K1, O1 etc.) using the standard formula:

```
h(t) = Z0 + Σ Hᵢ × cos(σᵢ·t + V0ᵢ − gᵢ)
```

where `σᵢ` is the constituent speed in °/hr, `V0ᵢ` is the astronomical argument at J2000, and `gᵢ` is the phase lag from the station's harmonic constants.

### Stream Speed Estimation

Tidal stream speed is estimated from the rate of change of height (dh/dt) using the Admiralty method:

```
stream_speed = K × |dh/dt|

where K = (T_M2 × max_spring_speed) / (π × spring_range)
```

This scales the height rate against known spring tide parameters to give a stream speed in knots, then projects it onto each leg's heading to get the fair/foul component.

### Route Optimiser

For each candidate departure time:
1. Walks each leg of the route at the set vessel speed through water
2. Finds the nearest tidal station to the leg midpoint
3. Looks up the stream vector (speed + flood/ebb direction) at the time the vessel reaches that leg
4. Adjusts the effective speed (`vessel_speed + stream_component`)
5. Accumulates the actual elapsed time to give a realistic ETA

**Scoring:**
```
weighted_fair = Σ distance × (1 + stream_component / vessel_speed)   [fair legs]
weighted_foul = Σ distance × |stream_component / vessel_speed|        [foul legs]

raw_score = (weighted_fair − weighted_foul × 0.5) / total_distance
score = clamp(50 + raw_score × 50, 0, 100)
```

Scores above 75 = **Excellent**, 50–75 = **Good**, 25–50 = **Fair**, below 25 = **Poor**.

---

## Installation

### Requirements

- Python 3.10+
- A free UKHO Admiralty API key (Discovery tier) — register at [admiraltyapi.portal.azure.com](https://admiraltyapi.portal.azure.com/)

### Quick start (any platform)

```bash
git clone https://github.com/mikekolling1966/tidalplan.git
cd tidalplan
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your UKHO_API_KEY
python start.py
```

Then open **http://localhost:8081** in a browser.

---

### Raspberry Pi / Signal K server install

SSH into your Pi and run the one-line installer:

```bash
curl -sSL https://raw.githubusercontent.com/mikekolling1966/tidalplan/main/install.sh | bash
```

This will:
1. Clone the repo to `/opt/tidalplan`
2. Create a Python virtual environment
3. Install all dependencies
4. Prompt for your UKHO API key
5. Install and enable a `systemd` service that starts automatically on boot

TidalPlan will then be available at **http://\<pi-ip\>:8081** from any device on the boat network.

To check the service status:
```bash
sudo systemctl status tidalplan
```

To view logs:
```bash
sudo journalctl -u tidalplan -f
```

---

### Docker (optional)

```bash
cp .env.example .env   # add your UKHO_API_KEY
docker compose up -d
```

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `UKHO_API_KEY` | UKHO Admiralty Discovery API key | *(required)* |

Set in the `.env` file in the project root.

---

## API Limits

The UKHO Discovery tier is **free** and allows **10,000 requests/month**. Station lists are cached to disk after the first fetch. Tidal event data is cached in memory per session. Normal usage (a few analyses per day) uses well under 100 requests/month.

---

## Project Structure

```
tidalplan/
├── app/
│   ├── main.py               # FastAPI app, static file serving
│   ├── config.py             # API key loading from .env
│   ├── routers/
│   │   ├── tides.py          # /api/tides/* endpoints
│   │   ├── routing.py        # /api/route/analyse endpoint
│   │   └── vessel.py         # /api/vessel/* (Signal K stub)
│   └── services/
│       ├── ukho.py           # UKHO Admiralty API client + caching
│       ├── harmonics.py      # TICON-4 harmonic tidal prediction
│       ├── gpx_parser.py     # Robust GPX parsing (handles OpenCPN namespaces)
│       └── optimizer.py      # Departure window scoring engine
├── data/
│   └── ticon4_channel.json   # TICON-4 harmonic constants for 13 Channel stations
├── frontend/
│   ├── index.html
│   ├── app.js                # Leaflet map, analysis UI, results table
│   └── style.css
├── start.py                  # Launch script
├── install.sh                # RPi/Linux one-line installer
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Tidal Stations (TICON-4)

| Station | Country |
|---|---|
| Cherbourg | France |
| Calais | France |
| Dunkirk | France |
| Dieppe | France |
| Le Havre | France |
| Brest | France |
| Saint-Malo | France |
| Vlissingen | Netherlands |
| Hoek van Holland | Netherlands |
| Den Helder | Netherlands |
| IJmuiden | Netherlands |
| Zeebrugge | Belgium |
| Ostend | Belgium |

UK stations are served by the UKHO API (608 stations).

---

## Licence

MIT — free to use, modify and distribute.

Built by Mike Kolling. Tidal harmonic data from [TICON-4](https://www.bodc.ac.uk/data/published_data_library/catalogue/10.5285/b7bfc082-e849-11e8-b9a3-00163e251233/) (CC BY 4.0).
