'use strict';

// ── map setup ─────────────────────────────────────────────────────────────
const map = L.map('map', { zoomControl: true }).setView([51.2, 1.5], 7);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 18,
}).addTo(map);

// ── state ─────────────────────────────────────────────────────────────────
let routeLayer    = null;
let stationLayer  = L.layerGroup().addTo(map);
let drawMarkers   = [];
let gpxCoords     = [];
let isDrawing     = false;
let allStations   = [];
let lastResults   = null;
let selectedRow   = -1;
let tideChartInst = null;

// ── default datetime (now → now+7d) ──────────────────────────────────────
(function initDatetimes() {
  const pad = n => String(n).padStart(2, '0');
  const fmtDay = d => `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())}`;
  // Default: tomorrow midnight UTC to tomorrow 23:30 UTC
  const tomorrow = new Date(Date.now() + 86400e3);
  const day = fmtDay(tomorrow);
  document.getElementById('start-dt').value = `${day}T00:00`;
  document.getElementById('end-dt').value   = `${day}T23:30`;
})();

// ── toast ─────────────────────────────────────────────────────────────────
function toast(msg, type = '') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 3500);
}

// ── GPX file drop / select ────────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');
const gpxInput = document.getElementById('gpx-input');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('active'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('active'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('active');
  const file = e.dataTransfer.files[0];
  if (file) loadGpxFile(file);
});
gpxInput.addEventListener('change', () => { if (gpxInput.files[0]) loadGpxFile(gpxInput.files[0]); });

let loadedGpxFile = null;

function loadGpxFile(file) {
  document.getElementById('gpx-filename').textContent = file.name;
  // Parse locally for map preview using a simple regex extract
  const reader = new FileReader();
  reader.onload = e => {
    previewGpxOnMap(e.target.result);
    // IMPORTANT: set loadedGpxFile AFTER previewGpxOnMap(), because that
    // function calls clearRoute() which would null it out if set earlier.
    loadedGpxFile = file;
    console.log('[GPX] loadedGpxFile set:', file.name);
  };
  reader.readAsText(file);
}

function previewGpxOnMap(gpxText) {
  clearRoute();
  const coords = [];
  // Extract all trkpt/rtept/wpt lat/lon
  const re = /(?:trkpt|rtept|wpt)[^>]*lat="([^"]+)"[^>]*lon="([^"]+)"/gi;
  let m;
  while ((m = re.exec(gpxText)) !== null) {
    coords.push([parseFloat(m[1]), parseFloat(m[2])]);
  }
  if (coords.length < 2) { toast('GPX has fewer than 2 points — nothing to show.', 'error'); return; }

  gpxCoords = coords;
  routeLayer = L.polyline(coords, { color: '#1a6b7a', weight: 3, opacity: .9 }).addTo(map);
  coords.forEach((c, i) => {
    const icon = L.divIcon({
      className: '',
      html: `<div style="width:10px;height:10px;border-radius:50%;background:${i===0?'#00c9a7':i===coords.length-1?'#e74c3c':'#1a6b7a'};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
      iconAnchor: [5, 5],
    });
    L.marker(c, { icon }).addTo(map);
  });
  map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
  toast(`Route loaded: ${coords.length} waypoints`, 'success');
}

function clearRoute() {
  if (routeLayer) { map.eachLayer(l => { if (l instanceof L.Polyline || (l instanceof L.Marker && !l._isStation)) map.removeLayer(l); }); routeLayer = null; }
  drawMarkers.forEach(m => map.removeLayer(m));
  drawMarkers = [];
  gpxCoords = [];
  loadedGpxFile = null;
  document.getElementById('gpx-filename').textContent = '';
  document.getElementById('results-wrap').innerHTML = '<div style="color:#6b8096;padding:20px;text-align:center">Load a GPX route and click <strong>Find Best Departure</strong></div>';
  document.getElementById('results-meta').textContent = 'No analysis run yet';
  document.getElementById('export-btn').style.display = 'none';
  lastResults = null;
}

function reverseRoute() {
  if (gpxCoords.length >= 2) {
    gpxCoords.reverse();
    map.eachLayer(l => { if (l instanceof L.Polyline || (l instanceof L.Marker && !l._isStation)) map.removeLayer(l); });
    routeLayer = L.polyline(gpxCoords, { color: '#1a6b7a', weight: 3, opacity: .9 }).addTo(map);
    gpxCoords.forEach((c, i) => {
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:10px;height:10px;border-radius:50%;background:${i===0?'#00c9a7':i===gpxCoords.length-1?'#e74c3c':'#1a6b7a'};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
        iconAnchor: [5, 5],
      });
      L.marker(c, { icon }).addTo(map);
    });
    loadedGpxFile = null;
    toast('Route reversed', 'success');
  } else if (drawMarkers.length >= 2) {
    drawMarkers.reverse();
    updateDrawRoute();
    toast('Route reversed', 'success');
  } else {
    toast('No route to reverse.', 'error');
  }
}

// ── draw mode ─────────────────────────────────────────────────────────────
function toggleDrawMode() {
  isDrawing = !isDrawing;
  const btn = document.getElementById('draw-btn');
  btn.textContent = isDrawing ? '✅ Done drawing' : '✏️ Draw';
  btn.style.background = isDrawing ? '#cce5ff' : '';
  map.getContainer().style.cursor = isDrawing ? 'crosshair' : '';
}

map.on('click', e => {
  if (!isDrawing) return;
  const m = L.marker([e.latlng.lat, e.latlng.lng], {
    draggable: true,
    icon: L.divIcon({
      className: '',
      html: `<div style="width:12px;height:12px;border-radius:50%;background:#00c9a7;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
      iconAnchor: [6, 6],
    }),
  }).addTo(map);
  drawMarkers.push(m);
  m.on('dragend', updateDrawRoute);
  updateDrawRoute();
});

function updateDrawRoute() {
  if (routeLayer) map.removeLayer(routeLayer);
  if (drawMarkers.length < 2) return;
  const coords = drawMarkers.map(m => [m.getLatLng().lat, m.getLatLng().lng]);
  routeLayer = L.polyline(coords, { color: '#1a6b7a', weight: 3 }).addTo(map);
}

// ── Wind GRIB ─────────────────────────────────────────────────────────────
const gribDropZone = document.getElementById('grib-drop-zone');
const gribInput    = document.getElementById('grib-input');

gribDropZone.addEventListener('dragover', e => { e.preventDefault(); gribDropZone.classList.add('active'); });
gribDropZone.addEventListener('dragleave', () => gribDropZone.classList.remove('active'));
gribDropZone.addEventListener('drop', e => {
  e.preventDefault();
  gribDropZone.classList.remove('active');
  const file = e.dataTransfer.files[0];
  if (file) uploadWindGrib(file);
});
gribInput.addEventListener('change', () => { if (gribInput.files[0]) uploadWindGrib(gribInput.files[0]); });

async function uploadWindGrib(file) {
  document.getElementById('grib-filename').textContent = file.name;
  setWindBadge('checking', 'Uploading…');
  document.getElementById('wind-detail').textContent = '';

  const fd = new FormData();
  fd.append('grib_file', file);
  try {
    const r = await fetch('/api/wind/upload', { method: 'POST', body: fd });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText); }
    const d = await r.json();
    setWindBadge('active', 'Wind data loaded');
    document.getElementById('wind-detail').innerHTML =
      `${d.steps} time steps<br>${d.time_start} → ${d.time_end}`;
    document.getElementById('clear-wind-btn').style.display = '';
    toast(`Wind GRIB loaded — ${d.steps} steps`, 'success');
  } catch (err) {
    setWindBadge('error', 'Load failed');
    document.getElementById('wind-detail').textContent = err.message;
    document.getElementById('grib-filename').textContent = '';
    toast(`Wind GRIB error: ${err.message}`, 'error');
  }
}

function setWindBadge(cls, label) {
  document.getElementById('wind-badge').className = `cmems-badge cmems-${cls}`;
  document.getElementById('wind-badge-label').textContent = label;
}

async function clearWindGrib() {
  await fetch('/api/wind/clear', { method: 'DELETE' });
  document.getElementById('grib-filename').textContent = '';
  document.getElementById('wind-detail').textContent = '';
  document.getElementById('clear-wind-btn').style.display = 'none';
  setWindBadge('fallback', 'No wind data loaded');
  toast('Wind data cleared', '');
}

async function checkWindStatus() {
  try {
    const r = await fetch('/api/wind/status');
    const d = await r.json();
    if (d.loaded) {
      setWindBadge('active', 'Wind data loaded');
      document.getElementById('wind-detail').innerHTML =
        `${d.steps} time steps<br>${d.time_start} → ${d.time_end}`;
      document.getElementById('clear-wind-btn').style.display = '';
    }
  } catch { /* server may not have cfgrib — badge stays at default */ }
}
checkWindStatus();

function degreesToCompass(deg) {
  const pts = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
  return pts[Math.round(deg / 22.5) % 16];
}

// ── CMEMS status ──────────────────────────────────────────────────────
async function checkCmemsStatus() {
  const badge  = document.getElementById('cmems-badge');
  const detail = document.getElementById('cmems-detail');
  try {
    const r = await fetch('/api/tides/cmems/status');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();

    if (d.available) {
      badge.className = 'cmems-badge cmems-active';
      badge.querySelector('.cmems-label').textContent = 'CMEMS model active';
      const from = d.forecast_start ? fmtDt(d.forecast_start) : '—';
      const to   = d.forecast_end   ? fmtDt(d.forecast_end)   : '—';
      const age  = d.age_hours != null ? `${d.age_hours.toFixed(1)}h old` : '';
      detail.innerHTML = `1.5 km hydrodynamic model<br>${from} → ${to}<br>${age}`;
    } else {
      badge.className = 'cmems-badge cmems-fallback';
      badge.querySelector('.cmems-label').textContent = 'Station fallback';
      detail.textContent = d.reason || 'CMEMS data not loaded — using tidal stream atlas estimates.';
    }
  } catch {
    badge.className = 'cmems-badge cmems-error';
    badge.querySelector('.cmems-label').textContent = 'Status unknown';
    detail.textContent = 'Could not reach status endpoint.';
  }
}
checkCmemsStatus();

// ── drag-to-resize results panel ──────────────────────────────────────
(function initResizeHandle() {
  const handle = document.getElementById('results-resize-handle');
  const panel  = document.getElementById('results-panel');
  if (!handle || !panel) return;

  let startY = 0, startH = 0;

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startY = e.clientY;
    startH = panel.offsetHeight;
    handle.classList.add('dragging');

    function onMove(ev) {
      // dragging up increases height (panel is at bottom, growing upwards)
      const delta = startY - ev.clientY;
      const minH = parseInt(getComputedStyle(panel).minHeight) || 120;
      const maxH = Math.round(window.innerHeight * 0.7);
      panel.style.height = Math.min(maxH, Math.max(minH, startH + delta)) + 'px';
    }
    function onUp() {
      handle.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  // Touch support
  handle.addEventListener('touchstart', e => {
    const touch = e.touches[0];
    startY = touch.clientY;
    startH = panel.offsetHeight;
    handle.classList.add('dragging');

    function onMove(ev) {
      const t = ev.touches[0];
      const delta = startY - t.clientY;
      const minH = parseInt(getComputedStyle(panel).minHeight) || 120;
      const maxH = Math.round(window.innerHeight * 0.7);
      panel.style.height = Math.min(maxH, Math.max(minH, startH + delta)) + 'px';
    }
    function onEnd() {
      handle.classList.remove('dragging');
      handle.removeEventListener('touchmove', onMove);
      handle.removeEventListener('touchend', onEnd);
    }
    handle.addEventListener('touchmove', onMove, { passive: true });
    handle.addEventListener('touchend', onEnd);
  }, { passive: true });
})();

// ── Signal K ──────────────────────────────────────────────────────────────
async function fetchVessel() {
  try {
    const r = await fetch('/api/vessel/data');
    const d = await r.json();
    const pill = document.getElementById('vessel-pill');
    if (d.position?.lat) {
      pill.innerHTML = `📍 ${d.position.lat.toFixed(4)}, ${d.position.lon.toFixed(4)}&nbsp;&nbsp;🚤 ${d.speed_knots ?? '—'} kt`;
      if (d.speed_knots) document.getElementById('vessel-speed').value = d.speed_knots.toFixed(1);
      toast('Vessel data loaded from Signal K', 'success');
    } else {
      pill.textContent = 'Signal K: no position data';
    }
  } catch {
    toast('Signal K not available', 'error');
  }
}

async function checkSkStatus() {
  try {
    const r = await fetch('/api/vessel/position');
    const d = await r.json();
    const el = document.getElementById('sk-status');
    el.textContent = d.lat ? `Signal K: ${d.lat.toFixed(4)}, ${d.lon.toFixed(4)}` : 'Signal K: connected, no fix';
  } catch {
    document.getElementById('sk-status').textContent = 'Signal K: offline';
  }
}
checkSkStatus();

// ── load stations ─────────────────────────────────────────────────────────
async function loadStations() {
  try {
    const r = await fetch('/api/tides/stations');
    allStations = await r.json();
    renderStationMarkers();
  } catch {
    toast('Could not load station list', 'error');
  }
}

function renderStationMarkers() {
  stationLayer.clearLayers();
  const showUkho  = document.getElementById('show-ukho').checked;
  const showTicon = document.getElementById('show-ticon').checked;

  allStations.forEach(s => {
    if (!s.lat || !s.lon) return;
    if (s.source === 'ukho'  && !showUkho)  return;
    if (s.source === 'ticon4' && !showTicon) return;

    const color = s.source === 'ukho' ? '#1a6b7a' : '#e67e22';
    const icon = L.divIcon({
      className: '',
      html: `<div style="width:8px;height:8px;border-radius:50%;background:${color};border:1.5px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)" title="${s.name}"></div>`,
      iconAnchor: [4, 4],
    });
    const marker = L.marker([s.lat, s.lon], { icon });
    marker._isStation = true;
    marker.bindPopup(`
      <strong>${s.name}</strong><br>
      Source: ${s.source === 'ukho' ? 'UKHO Admiralty' : 'TICON-4'}<br>
      ${s.country ? `Country: ${s.country}<br>` : ''}
      <button onclick="showTideChart('${s.id}','${s.name.replace(/'/g, '')}')" style="margin-top:6px;padding:4px 10px;background:#1a6b7a;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px">
        View tidal curve
      </button>
    `);
    stationLayer.addLayer(marker);
  });
}

function toggleStationLayer() { renderStationMarkers(); }

loadStations();

// ── analysis ──────────────────────────────────────────────────────────────
async function runAnalysis() {
  // Build waypoints from drawn markers or loaded GPX
  let hasRoute = routeLayer !== null;
  if (!hasRoute) { toast('Please load or draw a route first.', 'error'); return; }

  const startRaw = document.getElementById('start-dt').value;
  const endRaw   = document.getElementById('end-dt').value;
  if (!startRaw || !endRaw) { toast('Please set departure window dates.', 'error'); return; }

  const btn = document.getElementById('analyse-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Analysing…';

  document.getElementById('results-wrap').innerHTML = '<div class="spinner"></div>';
  document.getElementById('results-meta').textContent = 'Running…';

  try {
    let response;

    if (loadedGpxFile) {
      // Use file upload endpoint
      const fd = new FormData();
      fd.append('gpx_file', loadedGpxFile);
      fd.append('vessel_speed', document.getElementById('vessel-speed').value);
      fd.append('start_datetime', startRaw + ':00');
      fd.append('end_datetime',   endRaw   + ':00');
      fd.append('interval_minutes', document.getElementById('interval').value);
      fd.append('top_n', document.getElementById('top-n').value);
      response = await fetch('/api/route/analyse', { method: 'POST', body: fd });
    } else {
      // Use drawn waypoints or reversed-GPX coords via JSON endpoint
      const coords = drawMarkers.length > 0
        ? drawMarkers.map(m => [m.getLatLng().lat, m.getLatLng().lng])
        : gpxCoords;
      if (coords.length < 2) { toast('Draw at least 2 waypoints.', 'error'); return; }
      response = await fetch('/api/route/analyse-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          waypoints: coords,
          vessel_speed: parseFloat(document.getElementById('vessel-speed').value),
          start_datetime: startRaw + ':00',
          end_datetime:   endRaw   + ':00',
          interval_minutes: parseInt(document.getElementById('interval').value),
          top_n: parseInt(document.getElementById('top-n').value),
        }),
      });
    }

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || response.statusText);
    }

    const data = await response.json();
    lastResults = data;
    renderResults(data);
    if (data.warnings && data.warnings.length) {
      data.warnings.forEach(w => toast(`⚠️ ${w}`, ''));
    }
    toast(`Analysis complete — ${data.results.length} windows ranked`, 'success');

  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
    document.getElementById('results-wrap').innerHTML = `<div style="color:#e74c3c;padding:20px">Error: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '⚓ Find Best Departure';
  }
}

// ── render results ────────────────────────────────────────────────────────
let sortCol = 'duration';   // default: shortest passage first
let sortAsc = true;

function renderResults(data) {
  const meta = `${data.results.length} windows shown · ${data.windows_tested} tested`;
  document.getElementById('results-meta').textContent = meta;
  document.getElementById('export-btn').style.display = '';

  if (!data.results.length) {
    document.getElementById('results-wrap').innerHTML = '<div style="color:#6b8096;padding:20px">No results.</div>';
    return;
  }

  renderSortedTable(data.results);
}

function renderSortedTable(results) {
  // Sort a copy
  const sorted = [...results].sort((a, b) => {
    let av, bv;
    if (sortCol === 'duration')   { av = a.passage_hours;              bv = b.passage_hours; }
    else if (sortCol === 'score') { av = a.score;                      bv = b.score; }
    else if (sortCol === 'dep')   { av = new Date(a.departure).getTime(); bv = new Date(b.departure).getTime(); }
    else if (sortCol === 'eta')   { av = new Date(a.eta).getTime();    bv = new Date(b.eta).getTime(); }
    else                          { av = a.passage_hours;              bv = b.passage_hours; }
    return sortAsc ? av - bv : bv - av;
  });

  const arrow = dir => dir ? ' ▲' : ' ▼';
  const hdr = col => `style="cursor:pointer;user-select:none" onclick="sortBy('${col}')"`;

  const rows = sorted.map((w, i) => {
    const dep = fmtDt(w.departure);
    const eta = fmtDt(w.eta);
    const dur = `${Math.floor(w.passage_hours)}h ${Math.round((w.passage_hours % 1) * 60)}m`;
    const sc  = scoreBadge(w.score_label);
    const bar = scoreBar(w.score);
    const legInfo = w.legs.map(l => {
      const dir     = l.stream_component_kt >= 0 ? '↑' : '↓';
      const tag     = l.source === 'cmems' ? ' 📡' : '';
      const stn     = l.station || '—';
      const windStr = (l.wind_speed_kt || 0) > 0.3
        ? `  💨 ${degreesToCompass(l.wind_direction)} ${l.wind_speed_kt.toFixed(0)}kt`
        : '';
      return `Leg ${l.leg}: ${l.distance_nm}nm ${l.heading.toFixed(0)}°  ${dir} ${Math.abs(l.stream_component_kt).toFixed(1)}kt${windStr}  (${stn}${tag})`;
    }).join('\n');
    // store original result index for selectRow
    const origIdx = lastResults.results.indexOf(w);
    return `<tr data-idx="${origIdx}" onclick="selectRow(${origIdx})" title="${legInfo}">
      <td>${i+1}</td>
      <td><strong>${dep}</strong></td>
      <td>${eta}</td>
      <td>${dur}</td>
      <td>${bar}</td>
      <td>${sc}</td>
    </tr>`;
  }).join('');

  document.getElementById('results-wrap').innerHTML = `
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th ${hdr('dep')}>Departure (UTC)${sortCol==='dep' ? arrow(sortAsc) : ''}</th>
          <th ${hdr('eta')}>ETA (UTC)${sortCol==='eta' ? arrow(sortAsc) : ''}</th>
          <th ${hdr('duration')}>Duration${sortCol==='duration' ? arrow(sortAsc) : ''}</th>
          <th ${hdr('score')}>Tidal score${sortCol==='score' ? arrow(sortAsc) : ''}</th>
          <th>Rating</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function sortBy(col) {
  if (sortCol === col) {
    sortAsc = !sortAsc;   // toggle direction
  } else {
    sortCol = col;
    // Natural defaults: duration/dep/eta asc, score desc
    sortAsc = (col !== 'score');
  }
  if (lastResults) renderSortedTable(lastResults.results);
}

function selectRow(idx) {
  selectedRow = idx;
  document.querySelectorAll('tbody tr').forEach((r, i) => r.classList.toggle('selected', i === idx));
  const w = lastResults.results[idx];
  // Highlight tidal stations used in this window's legs
  const stationNames = new Set(w.legs.map(l => l.station));
  stationLayer.eachLayer(m => {
    if (m._popup) {
      const name = m.options.title || '';
      m.setOpacity(stationNames.has(name) ? 1.0 : 0.4);
    }
  });
}

function fmtDt(iso) {
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function scoreBadge(label) {
  const cls = { Excellent: 'excellent', Good: 'good', Fair: 'fair', Poor: 'poor' }[label] || 'fair';
  return `<span class="score-badge score-${cls}">${label}</span>`;
}

function scoreBar(score) {
  const pct = Math.round(score);
  const col = pct >= 75 ? '#27ae60' : pct >= 50 ? '#2980b9' : pct >= 25 ? '#f39c12' : '#e74c3c';
  return `<div style="display:flex;align-items:center;gap:6px">
    <div style="flex:1;height:8px;background:#eee;border-radius:4px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:${col};border-radius:4px"></div>
    </div>
    <span style="font-size:11px;font-weight:700;min-width:28px">${pct}</span>
  </div>`;
}

// ── tide chart ────────────────────────────────────────────────────────────
async function showTideChart(stationId, stationName) {
  const modal = document.getElementById('tide-chart-modal');
  document.getElementById('tide-chart-title').textContent = `Tidal curve — ${stationName}`;
  modal.classList.add('open');

  // 7-day window from analysis start or now
  const startEl = document.getElementById('start-dt').value;
  const start = startEl ? new Date(startEl + 'Z') : new Date();
  const end   = new Date(start.getTime() + 7 * 86400e3);
  const fmt   = d => d.toISOString().replace('.000Z', '').replace('Z', '');

  try {
    const r = await fetch(`/api/tides/stations/${encodeURIComponent(stationId)}/heights?start=${fmt(start)}&end=${fmt(end)}&interval_minutes=20`);
    const pts = await r.json();
    const labels = pts.map(p => fmtDt(p.time));
    const values = pts.map(p => p.height);

    const canvas = document.getElementById('tide-chart-canvas');
    if (tideChartInst) tideChartInst.destroy();
    tideChartInst = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Height (m)',
          data: values,
          borderColor: '#1a6b7a',
          backgroundColor: 'rgba(26,107,122,0.1)',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          tension: 0.4,
        }],
      },
      options: {
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { maxTicksLimit: 8, font: { size: 10 } } },
          y: { title: { display: true, text: 'Height (m)' }, ticks: { font: { size: 10 } } },
        },
      },
    });
  } catch (err) {
    toast(`Could not load tidal curve: ${err.message}`, 'error');
    modal.classList.remove('open');
  }
}

function closeTideChart(e) {
  if (!e || e.target === document.getElementById('tide-chart-modal') || e.type !== 'click' && !e.target.closest) {
    document.getElementById('tide-chart-modal').classList.remove('open');
  }
  if (e && e.target === document.getElementById('tide-chart-modal')) {
    document.getElementById('tide-chart-modal').classList.remove('open');
  }
}

// ── CSV export ────────────────────────────────────────────────────────────
function exportResults() {
  if (!lastResults) return;
  const rows = [['Rank','Departure UTC','ETA UTC','Duration hrs','Score','Rating']];
  lastResults.results.forEach((w, i) => {
    rows.push([i+1, w.departure, w.eta, w.passage_hours, w.score, w.score_label]);
  });
  const csv = rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'tidal_departure_windows.csv';
  a.click();
}
