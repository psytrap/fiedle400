"""Self-contained HTML viewer for a decoded SpO2/pulse recording.

One static template (this module's _TEMPLATE constant) with the specific
recording's records injected as inline JSON at build time -- the page never
fetches anything else, so it works from a plain file:// open in any browser
with no server and no extra dependency (T-005).
"""

import json

from fiedle400 import desat
from fiedle400.export import pad_records

_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>fiedle400 recording</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2em; background: #fafafa; color: #222; }
  h1 { font-size: 1.1em; margin-bottom: 0.2em; }
  #meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
  #legend { margin-bottom: 0.5em; font-size: 0.9em; display: flex; align-items: center; gap: 1.5em; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.4em; }
  #resetZoom { display: none; font-size: 0.85em; color: #2b6cb0; cursor: pointer; text-decoration: underline; background: none; border: none; padding: 0; }
  #chartWrap { position: relative; }
  canvas { background: #fff; border: 1px solid #ddd; display: block; width: 100%; }
  #tooltip {
    position: absolute; display: none; pointer-events: none;
    background: #222; color: #fff; font-size: 0.8em; padding: 6px 8px;
    border-radius: 4px; white-space: nowrap; z-index: 2;
  }
  #stats { margin-top: 1em; border-collapse: collapse; font-size: 0.9em; }
  #stats th, #stats td { text-align: left; padding: 3px 1.2em 3px 0; }
  #stats th { color: #666; font-weight: normal; }
  #stats th.statsGroup { color: #000; font-weight: bold; padding-top: 0.6em; }
  #stats tr:first-child th.statsGroup { padding-top: 3px; }
  #legend label { cursor: pointer; user-select: none; }
  #legend input[type=checkbox] { margin-right: 0.4em; }
  #printBtn { font-size: 0.85em; margin-left: auto; cursor: pointer; }
  #desatLevel { width: 3.5em; }
  #dropPct, #minDur, #critLevel { width: 3.5em; }
  #pulseDropBpm, #pulseMinDur { width: 3.5em; }
  .paramTable { border-collapse: collapse; margin: 0.4em 0; }
  .paramTable td { padding: 1px 8px 1px 0; }
  .paramTable td:first-child { color: #666; }
  #pulseParamsTable td:first-child { color: #999; }
  .paramGroup { padding: 0.6em 0 0.2em; margin-top: 0.4em; border-top: 1px solid #e5e5e5; }
  .paramGroup:first-of-type { border-top: none; }
  @media print {
    body { margin: 0.5em; background: #fff; }
    #resetZoom, #printBtn, #legend input[type=checkbox] { display: none !important; }
    .dot { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    #tooltip { display: none !important; }
    canvas { border: 1px solid #999; }
  }
</style>
</head>
<body>
<h1>fiedle400 recording</h1>
<div id="meta"></div>
<div id="legend">
  <label><input type="checkbox" id="showSpo2" checked><span class="dot" style="background:#2b6cb0"></span>SpO2 (%, fixed 50-100)</label>
  <label><input type="checkbox" id="showHr" checked><span class="dot" style="background:#c05621"></span>Heart rate (bpm, fixed 30-220)</label>
  <button id="resetZoom">Reset zoom</button>
  <button id="printBtn" type="button">Print</button>
</div>
<div id="chartWrap">
  <canvas id="c" height="420"></canvas>
  <div id="tooltip"></div>
</div>
<table id="stats"></table>
<div id="levelGroup" class="paramGroup">
<table id="levelTable" class="paramTable" style="font-size:0.85em">
  <tr><td colspan="2"><strong>Time-below level</strong></td></tr>
  <tr><td id="levelRow">below</td><td><input type="number" id="desatLevel" min="50" max="99" step="1" value="90"> % SpO2</td></tr>
</table>
</div>
<div id="eventParamsGroup" class="paramGroup">
<table id="eventParamsTable" class="paramTable" style="font-size:0.85em">
  <tr><td colspan="2"><strong>Desaturation event</strong></td></tr>
  <tr><td>fall of at least</td><td><input type="number" id="dropPct" min="1" max="20" step="1"> %</td></tr>
  <tr><td>over</td><td><input type="number" id="minDur" min="1" max="180" step="1"> -180 s</td></tr>
  <tr><td>count event as severe if under</td><td><input type="number" id="critLevel" min="1" max="99" step="1"> %</td></tr>
</table>
<p id="eventParamsNote" style="font-size:0.85em;color:#666;margin:0.4em 0 0">(pulse-rate events: not decoded, SpO2 only -- T-025)</p>
</div>
<div id="pulseParamsGroup" class="paramGroup">
<table id="pulseParamsTable" class="paramTable" style="font-size:0.85em;color:#999">
  <tr><td colspan="2"><strong>Pulse-rate event</strong></td></tr>
  <tr><td>change of at least</td><td><input type="number" id="pulseDropBpm" min="2" max="20" step="1" value="6" disabled title="Dummy input: no pulse-rate detector is implemented yet, this value is not used (T-029/T-030)"> bpm</td></tr>
  <tr><td>over</td><td><input type="number" id="pulseMinDur" min="1" max="180" step="1" value="8" disabled title="Dummy input: no pulse-rate detector is implemented yet, this value is not used (T-029/T-030)"> s</td></tr>
</table>
<p id="pulseParamsNote" style="font-size:0.85em;color:#999;margin:0.4em 0 0">(dummy, not functional -- T-029/T-030)</p>
</div>
<script id="spo2-data" type="application/json">%%DATA%%</script>
<script id="spo2-events" type="application/json">%%EVENTS%%</script>
<script>
(function () {
  var records = JSON.parse(document.getElementById('spo2-data').textContent);
  // {events, summary, params}, computed in Python (desat.py) for the page's initial
  // load; re-derived here in JS (detectEvents/summarizeEvents, a 1:1 port of
  // desat.py's detect_events/summarize) whenever the event parameters below change,
  // so the page recomputes without a server round-trip (T-025).
  var analysis = JSON.parse(document.getElementById('spo2-events').textContent);
  var meta = document.getElementById('meta');
  var n = records.length;
  if (n === 0) {
    meta.textContent = 'No records in this recording.';
    return;
  }
  meta.textContent = n + ' record(s), ' + records[0].timestamp + ' to ' + records[n - 1].timestamp;
  var spo2Arr = records.map(function (r) { return r.spo2; });

  // Desaturation-event detection, ported from fiedle400/desat.py (SPO2_FORMAT.md
  // §7.2). max_time/max_avg/oscillation stay fixed, matching SpO2 Assistant's own
  // Analyseparameter dialog, which doesn't expose them either (T-019 screenshot).
  var EVT_MAX_TIME = 180, EVT_MAX_AVG = 2, EVT_OSCILLATION = 1, EVT_LO = 0, EVT_HI = 100, EVT_INVALID = 127;

  function detectEvents(spo2, drop, minTime) {
    var x = spo2.map(function (v) { return (v === null || v === undefined) ? EVT_INVALID : v; });
    var cands = [];
    var st = 0, en = 0;
    function finish() {
      if (st && en && en - st > 0) cands.push([st, en, x[st], x[en]]);
      st = 0; en = 0;
    }
    for (var i = 0; i < x.length; i++) {
      var v = x[i];
      if (v > EVT_HI || v < EVT_LO) { finish(); continue; }
      if (i === 0) continue;
      var p = x[i - 1];
      if (v > p) {
        finish();
      } else if (v === p) {
        if (st) en = i;
      } else if (st) {
        en = i;
      } else if (p > EVT_LO && p < EVT_HI) {
        st = i - 1; en = i;
      }
    }
    finish();

    function accepted(c) {
      var dur = c[1] - c[0], depth = c[2] - c[3];
      if (!dur || depth < drop || dur < minTime || dur > EVT_MAX_TIME) return false;
      if (!(Math.floor(depth / dur) < EVT_MAX_AVG)) return false;
      for (var k = c[0]; k <= c[1]; k++) { if (!(x[k] >= EVT_LO && x[k] <= EVT_HI)) return false; }
      return true;
    }

    var events = [];
    if (!cands.length) return events;
    var cur = cands[0].slice();
    for (var j = 1; j < cands.length; j++) {
      var nx = cands[j];
      if (nx[2] - cur[3] <= EVT_OSCILLATION && nx[3] < cur[3] && nx[2] < cur[2] && nx[0] - cur[1] <= minTime) {
        cur[1] = nx[1]; cur[3] = nx[3];
      } else {
        if (accepted(cur)) events.push(cur);
        cur = nx.slice();
      }
    }
    if (accepted(cur)) events.push(cur);
    return events.map(function (e) { return { start: e[0], nadir: e[1], from_pct: e[2], to_pct: e[3] }; });
  }

  function summarizeEvents(spo2, events, criteria) {
    var valid = [];
    for (var i = 0; i < spo2.length; i++) {
      var v = spo2[i];
      if (v !== null && v !== undefined && v >= 1 && v <= 100) valid.push(i);
    }
    var out = { samples: spo2.length, valid_samples: valid.length, total_event: events.length };
    if (!spo2.length) return out;
    function r2(v) { return Math.round(v * 100) / 100; }
    function r1(v) { return Math.round(v * 10) / 10; }
    function sum(a, f) { return a.reduce(function (s, e) { return s + f(e); }, 0); }
    var hours = spo2.length / 3600.0;
    out.index_per_hr = r2(events.length / hours);
    out.adjusted_index_per_hr = valid.length ? r2(events.length / (valid.length / 3600.0)) : null;
    out.artifact_pct = r2(100.0 * (spo2.length - valid.length) / spo2.length);
    out.avg_low_spo2 = events.length ? r2(sum(events, function (e) { return e.to_pct; }) / events.length) : null;
    var low = events.filter(function (e) { return e.to_pct < criteria; });
    out.events_below_criteria = low.length;
    out.avg_low_spo2_below_criteria = low.length ? r2(sum(low, function (e) { return e.to_pct; }) / low.length) : null;
    out.avg_event_duration_s = events.length ? r1(sum(events, function (e) { return e.nadir - e.start; }) / events.length) : null;
    var inside = {};
    events.forEach(function (e) { for (var k = e.start; k <= e.nadir; k++) inside[k] = true; });
    var basal = valid.filter(function (i) { return !inside[i]; }).map(function (i) { return spo2[i]; });
    if (!basal.length) basal = valid.map(function (i) { return spo2[i]; });
    out.basal_spo2 = basal.length ? r2(sum(basal, function (v) { return v; }) / basal.length) : null;
    return out;
  }

  function recomputeEvents() {
    var drop = parseFloat(document.getElementById('dropPct').value);
    var minTime = parseInt(document.getElementById('minDur').value, 10);
    var criteria = parseFloat(document.getElementById('critLevel').value);
    if (isNaN(drop) || drop < 1 || drop > 20) return;
    if (isNaN(minTime) || minTime < 1 || minTime > EVT_MAX_TIME) return;
    if (isNaN(criteria) || criteria < 1 || criteria > 99) return;
    var events = detectEvents(spo2Arr, drop, minTime);
    analysis = {
      events: events,
      summary: summarizeEvents(spo2Arr, events, criteria),
      params: { drop: drop, min_time: minTime, max_time: EVT_MAX_TIME, criteria: criteria },
    };
    stats(); render();
  }

  document.getElementById('dropPct').value = analysis.params.drop;
  document.getElementById('minDur').value = analysis.params.min_time;
  document.getElementById('critLevel').value = analysis.params.criteria;
  ['dropPct', 'minDur', 'critLevel'].forEach(function (id) {
    document.getElementById(id).addEventListener('input', recomputeEvents);
  });

  // Fixed ranges so different recordings are visually comparable, not
  // auto-scaled per file. SpO2 50-100% (below 50 is clamped, not expected
  // in practice); heart rate 30-220 bpm, a generic pulse-oximeter display
  // range covering rest through heavy exertion.
  var SPO2_LO = 50, SPO2_HI = 100;
  var HR_LO = 30, HR_HI = 220;
  var DESAT_THRESHOLD = 90; // default level for "time below"; changeable in the page (vendor: a user-chosen level)
  var show = { spo2: true, heart_rate: true }; // per-channel switches (checkboxes in the legend)

  var canvas = document.getElementById('c');
  var ctx = canvas.getContext('2d');
  var tooltip = document.getElementById('tooltip');
  var resetBtn = document.getElementById('resetZoom');
  var padL = 50, padR = 55, padT = 20, padB = 34;

  // Zoom window: [viewStart, viewEnd] indices into `records`, inclusive.
  // Horizontal-only responsiveness: canvas width follows the container;
  // height is fixed (set via the height="420" attribute), never stretched.
  var viewStart = 0, viewEnd = n - 1;
  var layout = null; // recomputed by render(): {W, plotW, plotH, padL, padT, dpr, viewStart, viewEnd}

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function fmtTime(ts) {
    var i = String(ts).indexOf('T');
    return i === -1 ? String(ts) : String(ts).slice(i + 1);
  }

  var CSS_HEIGHT = canvas.height; // fixed CSS height, read once; never changed by resize
                                   // (horizontal-only stretch) -- must not be re-read from
                                   // canvas.height after the first render, since that attribute
                                   // gets overwritten with the DPR-scaled pixel buffer size below.
  function render() {
    var cssWidth = canvas.parentElement.clientWidth;
    var cssHeight = CSS_HEIGHT;
    var dpr = window.devicePixelRatio || 1;
    // Both the pixel buffer (canvas.width/height) and the CSS display size
    // must be set for a sharp, correctly-clipped render at any DPR -- scaling
    // only the width here previously left the buffer too short vertically,
    // silently clipping anything below CSS y ~= cssHeight / dpr (the x-axis
    // time labels included).
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    var plotW = cssWidth - padL - padR, plotH = cssHeight - padT - padB;
    var vs = viewStart, ve = viewEnd, count = ve - vs + 1;

    function x(i) { return padL + (count <= 1 ? 0 : ((i - vs) / (count - 1)) * plotW); }
    function ySpo2(v) { return padT + (1 - (clamp(v, SPO2_LO, SPO2_HI) - SPO2_LO) / (SPO2_HI - SPO2_LO)) * plotH; }
    function yHr(v) { return padT + (1 - (clamp(v, HR_LO, HR_HI) - HR_LO) / (HR_HI - HR_LO)) * plotH; }

    layout = { cssWidth: cssWidth, plotW: plotW, plotH: plotH, padL: padL, padT: padT, padB: padB, x: x, vs: vs, ve: ve, count: count };

    // Axes
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, padT); ctx.lineTo(padL, padT + plotH); ctx.lineTo(padL + plotW, padT + plotH);
    ctx.stroke();

    // Horizontal gridlines + SpO2 labels (left)
    ctx.font = '11px sans-serif';
    ctx.strokeStyle = '#eee';
    ctx.fillStyle = '#2b6cb0';
    for (var sv = SPO2_LO; sv <= SPO2_HI; sv += 10) {
      var syy = ySpo2(sv);
      ctx.beginPath(); ctx.moveTo(padL, syy); ctx.lineTo(padL + plotW, syy); ctx.stroke();
      if (show.spo2) ctx.fillText(sv + '%', 4, syy + 4);
    }

    // Heart-rate labels (right), skipping any that would overlap
    ctx.fillStyle = '#c05621';
    var lastLabelY = null;
    for (var hv = HR_LO; show.heart_rate && hv <= HR_HI; hv += 40) {
      var hyy = yHr(hv);
      if (lastLabelY !== null && Math.abs(hyy - lastLabelY) < 14) continue;
      ctx.fillText(Math.round(hv) + '', padL + plotW + 6, hyy + 4);
      lastLabelY = hyy;
    }

    // X-axis time ticks: ~6 evenly spaced across the visible range
    var tickCount = Math.min(6, count);
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    for (var t = 0; t < tickCount; t++) {
      var idx = vs + Math.round((t / Math.max(1, tickCount - 1)) * (count - 1));
      var tx = x(idx);
      ctx.strokeStyle = '#f2f2f2';
      ctx.beginPath(); ctx.moveTo(tx, padT); ctx.lineTo(tx, padT + plotH); ctx.stroke();
      ctx.fillText(fmtTime(records[idx].timestamp), tx, padT + plotH + 16);
    }
    ctx.textAlign = 'left';

    function drawSeries(key, color, yFn) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      var drawing = false;
      for (var i = vs; i <= ve; i++) {
        var v = records[i][key];
        if (v === null || v === undefined) { drawing = false; continue; }
        var px = x(i), py = yFn(v);
        if (!drawing) { ctx.moveTo(px, py); drawing = true; } else { ctx.lineTo(px, py); }
      }
      ctx.stroke();
    }

    // Desaturation events (SpO2 Assistant's method): shaded from the start of the fall to the nadir.
    if (show.spo2) {
      ctx.fillStyle = 'rgba(197,48,48,0.18)';
      analysis.events.forEach(function (e) {
        if (e.nadir < vs || e.start > ve) return;
        var x0 = x(Math.max(e.start, vs)), x1 = x(Math.min(e.nadir, ve));
        ctx.fillRect(x0, padT, Math.max(2, x1 - x0), plotH);
      });
    }

    if (show.spo2) drawSeries('spo2', '#2b6cb0', ySpo2);
    if (show.heart_rate) drawSeries('heart_rate', '#c05621', yHr);

    resetBtn.style.display = (vs === 0 && ve === n - 1) ? 'none' : 'inline';
  }

  function nearestIndex(mouseX) {
    if (!layout) return null;
    var frac = clamp((mouseX - layout.padL) / layout.plotW, 0, 1);
    return clamp(layout.vs + Math.round(frac * (layout.count - 1)), layout.vs, layout.ve);
  }

  // Hover tooltip: shows the exact reading at the nearest point.
  canvas.addEventListener('mousemove', function (ev) {
    if (dragStartX !== null) { handleDrag(ev); return; }
    var rect = canvas.getBoundingClientRect();
    var mx = ev.clientX - rect.left;
    var idx = nearestIndex(mx);
    if (idx === null) return;
    var r = records[idx];
    tooltip.style.display = 'block';
    tooltip.style.left = (mx + 12) + 'px';
    tooltip.style.top = (ev.clientY - rect.top - 10) + 'px';
    tooltip.innerHTML = fmtTime(r.timestamp) +
      (show.spo2 ? '<br>SpO2: ' + (r.spo2 === null ? '--' : r.spo2 + '%') : '') +
      (show.heart_rate ? '<br>HR: ' + (r.heart_rate === null ? '--' : r.heart_rate + ' bpm') : '');
  });
  canvas.addEventListener('mouseleave', function () { tooltip.style.display = 'none'; });

  // Click-drag to zoom into a horizontal range; reset link restores the full view.
  var dragStartX = null, dragStartIdx = null;
  var selectionDiv = document.createElement('div');
  selectionDiv.style.cssText = 'position:absolute;top:0;bottom:0;background:rgba(43,108,176,0.12);border-left:1px solid #2b6cb0;border-right:1px solid #2b6cb0;display:none;pointer-events:none;';
  document.getElementById('chartWrap').appendChild(selectionDiv);

  canvas.addEventListener('mousedown', function (ev) {
    var rect = canvas.getBoundingClientRect();
    dragStartX = ev.clientX - rect.left;
    dragStartIdx = nearestIndex(dragStartX);
    selectionDiv.style.display = 'block';
    selectionDiv.style.left = dragStartX + 'px';
    selectionDiv.style.width = '0px';
  });

  function handleDrag(ev) {
    var rect = canvas.getBoundingClientRect();
    var mx = ev.clientX - rect.left;
    var left = Math.min(dragStartX, mx), width = Math.abs(mx - dragStartX);
    selectionDiv.style.left = left + 'px';
    selectionDiv.style.width = width + 'px';
  }

  window.addEventListener('mouseup', function (ev) {
    if (dragStartX === null) return;
    var rect = canvas.getBoundingClientRect();
    var mx = clamp(ev.clientX - rect.left, 0, rect.width);
    var endIdx = nearestIndex(mx);
    selectionDiv.style.display = 'none';
    var dragged = Math.abs(mx - dragStartX) > 6; // ignore accidental tiny drags (treat as a click)
    dragStartX = null;
    if (dragged && endIdx !== null && dragStartIdx !== null && endIdx !== dragStartIdx) {
      viewStart = Math.min(dragStartIdx, endIdx);
      viewEnd = Math.max(dragStartIdx, endIdx);
      render();
    }
  });

  resetBtn.addEventListener('click', function () {
    viewStart = 0; viewEnd = n - 1;
    render();
  });

  window.addEventListener('resize', render); // horizontal-only: render() keeps height fixed

  // Session statistics, computed over the whole recording regardless of zoom.
  function stats() {
    var spo2Vals = records.map(function (r) { return r.spo2; }).filter(function (v) { return v !== null && v !== undefined; });
    var hrVals = records.map(function (r) { return r.heart_rate; }).filter(function (v) { return v !== null && v !== undefined; });
    var invalidCount = n - spo2Vals.length;
    var desatCount = spo2Vals.filter(function (v) { return v < DESAT_THRESHOLD; }).length;
    function avg(a) { return a.length ? (a.reduce(function (s, v) { return s + v; }, 0) / a.length) : null; }
    function fmtSec(s) {
      var m = Math.floor(s / 60), ss = s % 60;
      return m + 'm ' + ss + 's';
    }
    var rows = [
      ['__group__', 'Recording'],
      ['Duration', fmtSec(n) + ' (' + n + ' records)'],
      ['SpO2 min / avg / max', spo2Vals.length ? Math.min.apply(null, spo2Vals) + '% / ' + avg(spo2Vals).toFixed(1) + '% / ' + Math.max.apply(null, spo2Vals) + '%' : 'n/a'],
      ['Heart rate min / avg / max', hrVals.length ? Math.min.apply(null, hrVals) + ' / ' + avg(hrVals).toFixed(1) + ' / ' + Math.max.apply(null, hrVals) + ' bpm' : 'n/a'],
      ['No-signal / probe-out', fmtSec(invalidCount) + ' (' + (100 * invalidCount / n).toFixed(1) + '%)'],
    ];
    var a = analysis.summary;
    function f1(v, unit) { return v === null || v === undefined ? 'n/a' : v.toFixed(1) + unit; }
    rows.push(
      ['__group__', 'Desaturation analysis'],
      ['Event index', f1(a.index_per_hr, ' /hr') + ' (adjusted ' + f1(a.adjusted_index_per_hr, ' /hr') + ')'],
      ['Desaturation events', a.total_event + ' (red bands; fall of at least ' + analysis.params.drop + '% over ' + analysis.params.min_time + '-' + analysis.params.max_time + ' s, SpO2 Assistant method)'],
      ['Events below ' + analysis.params.criteria + '%', a.events_below_criteria + (a.avg_low_spo2_below_criteria === null ? '' : ' (average low ' + f1(a.avg_low_spo2_below_criteria, '%') + ')')],
      ['Average lowest SpO2 of events', f1(a.avg_low_spo2, '%')],
      ['Basal SpO2 (estimate)', f1(a.basal_spo2, '%') + ' (mean outside event falls; the exact SpO2 Assistant rule is not confirmed)'],
      ['Time below ' + DESAT_THRESHOLD + '% SpO2', fmtSec(desatCount) + (spo2Vals.length ? ' (' + (100 * desatCount / spo2Vals.length).toFixed(1) + '% of valid readings)' : '')]
    );
    var table = document.getElementById('stats');
    table.innerHTML = rows.map(function (r) {
      if (r[0] === '__group__') return '<tr><th colspan="2" class="statsGroup">' + r[1] + '</th></tr>';
      return '<tr><th>' + r[0] + '</th><td>' + r[1] + '</td></tr>';
    }).join('');
  }

  document.getElementById('showSpo2').addEventListener('change', function (ev) {
    show.spo2 = ev.target.checked; render();
  });
  document.getElementById('showHr').addEventListener('change', function (ev) {
    show.heart_rate = ev.target.checked; render();
  });
  document.getElementById('desatLevel').addEventListener('input', function (ev) {
    var v = parseInt(ev.target.value, 10);
    if (isNaN(v) || v < 50 || v > 99) return; // ignore half-typed or out-of-range values
    DESAT_THRESHOLD = v; stats();
  });
  // Print uses the browser's own dialog; the canvas is redrawn at the print
  // width first (see the @media print rules above).
  document.getElementById('printBtn').addEventListener('click', function () { window.print(); });
  window.addEventListener('beforeprint', render);
  window.addEventListener('afterprint', render);

  stats();
  render();
})();
</script>
</body>
</html>
"""


def build_viewer_html(records):
    """Builds a self-contained HTML page with `records` injected as inline JSON.

    `records` is the list of dicts fiedle400's engine/export already produce
    (timestamp, spo2, heart_rate, flags, ...); only the fields the template
    actually uses are kept, so other callers' extra dict keys never leak in.
    Escapes `<` in the JSON so a value can never prematurely close the
    `<script>` tag it's embedded in -- defensive; none of this data can
    contain it today, but it costs nothing to not depend on that staying true.
    """
    # One entry per elapsed second (T-022): the chart places records by list index and the
    # event detector treats neighbours as one second apart, so a pause between two stored
    # sessions has to be present as probe-out records or it is drawn/analysed as a fall.
    records = pad_records(records)
    payload = [
        {
            "timestamp": r.get("timestamp"),
            "spo2": r.get("spo2"),
            "heart_rate": r.get("heart_rate"),
            "flags": r.get("flags"),
        }
        for r in records
    ]
    data_json = json.dumps(payload).replace("<", "\\u003c")
    spo2 = [p["spo2"] for p in payload]
    events = desat.detect_events(spo2)
    analysis = {
        "events": events,
        "summary": desat.summarize(spo2, events),
        "params": {
            "drop": desat.DROP,
            "min_time": desat.MIN_TIME,
            "max_time": desat.MAX_TIME,
            "criteria": desat.CRITERIA,
        },
    }
    events_json = json.dumps(analysis).replace("<", "\\u003c")
    return _TEMPLATE.replace("%%DATA%%", data_json).replace("%%EVENTS%%", events_json)
