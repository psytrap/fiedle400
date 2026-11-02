"""Self-contained HTML viewer for a decoded SpO2/pulse recording.

One static template (this module's _TEMPLATE constant) with the specific
recording's records injected as inline JSON at build time -- the page never
fetches anything else, so it works from a plain file:// open in any browser
with no server and no extra dependency (T-005).
"""

import json

from fiedle400 import desaturation
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
  #chartWrapper { position: relative; }
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
  #printButton { font-size: 0.85em; margin-left: auto; cursor: pointer; }
  #dropPercent, #minimumTime, #criteriaLevel, #maximumTimeFixed { width: 3.5em; }
  #maximumTimeFixed { color: #999; background: #f5f5f5; }
  #pulseDropBpm, #pulseMinimumTime { width: 3.5em; }
  .parameterTable { border-collapse: collapse; margin: 0.4em 0; }
  .parameterTable td { padding: 1px 8px 1px 0; }
  .parameterTable td:first-child { color: #666; }
  .parameterGroup { padding: 0.6em 0 0.2em; margin-top: 0.4em; border-top: 1px solid #e5e5e5; }
  .parameterGroup:first-of-type { border-top: none; }
  @media print {
    body { margin: 0.5em; background: #fff; }
    #resetZoom, #printButton, #legend input[type=checkbox] { display: none !important; }
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
  <label><input type="checkbox" id="showSpo2" checked><span class="dot" style="background:#2b6cb0"></span>SpO2 (%, range 50-100)</label>
  <label><input type="checkbox" id="showHeartRate" checked><span class="dot" style="background:#c05621"></span>Heart rate (bpm, range 30-220)</label>
  <button id="resetZoom">Reset zoom</button>
  <button id="printButton" type="button">Print</button>
</div>
<div id="chartWrapper">
  <canvas id="chart" height="420"></canvas>
  <div id="tooltip"></div>
</div>
<table id="stats"></table>
<div id="eventParametersGroup" class="parameterGroup">
<table id="eventParametersTable" class="parameterTable" style="font-size:0.85em">
  <tr><td colspan="2"><strong>Desaturation event</strong></td></tr>
  <tr><td>fall of at least</td><td><input type="number" id="dropPercent" min="1" max="20" step="1"> %</td></tr>
  <tr><td>over</td><td><input type="number" id="minimumTime" min="1" max="180" step="1"> - <input type="number" id="maximumTimeFixed" value="180" readonly title="Fixed by SpO2 Assistant, not adjustable (SPO2_FORMAT.md Sec7.2)"> s</td></tr>
  <tr><td>count event as severe if under</td><td><input type="number" id="criteriaLevel" min="1" max="99" step="1"> %</td></tr>
</table>
</div>
<div id="pulseParametersGroup" class="parameterGroup">
<table id="pulseParametersTable" class="parameterTable" style="font-size:0.85em">
  <tr><td colspan="2"><strong>Pulse-rate event</strong></td></tr>
  <tr><td>fall of at least</td><td><input type="number" id="pulseDropBpm" min="2" max="20" step="1"> bpm</td></tr>
  <tr><td>over</td><td><input type="number" id="pulseMinimumTime" min="1" max="180" step="1"> - 180 s</td></tr>
</table>
</div>
<script id="spo2-data" type="application/json">%%DATA%%</script>
<script id="spo2-events" type="application/json">%%EVENTS%%</script>
<script>
(function () {
  var records = JSON.parse(document.getElementById('spo2-data').textContent);
  // {events, summary, parameters, pulse: {events, summary, parameters}}, computed in Python (desaturation.py) for the page's initial
  // load; re-derived here in JS (detectEvents/summarizeEvents, a 1:1 port of
  // desaturation.py's detect_events/summarize) whenever the event parameters below change,
  // so the page recomputes without a server round-trip (T-025).
  var analysis = JSON.parse(document.getElementById('spo2-events').textContent);
  var meta = document.getElementById('meta');
  var recordCount = records.length;
  if (recordCount === 0) {
    meta.textContent = 'No records in this recording.';
    return;
  }
  function formatTimestamp(timestamp) { return timestamp == null ? timestamp : String(timestamp).replace('T', ' '); }
  function formatSeconds(totalSeconds) {
    var minutes = Math.floor(totalSeconds / 60), seconds = totalSeconds % 60;
    return minutes + 'm ' + seconds + 's';
  }
  meta.textContent = formatTimestamp(records[0].timestamp) + ' to ' + formatTimestamp(records[recordCount - 1].timestamp) + ' -- duration ' + formatSeconds(recordCount);
  var spo2Series = records.map(function (record) { return record.spo2; });
  var pulseSeries = records.map(function (record) { return record.heart_rate; });

  // BEGIN desaturation-port (extracted and run under Node by tests/test_desaturation_js_parity.py, T-027)
  // Desaturation-event detection, ported from fiedle400/desaturation.py (SPO2_FORMAT.md
  // §7.2). max_time/max_avg/oscillation stay fixed, matching SpO2 Assistant's own
  // Analyseparameter dialog, which doesn't expose them either (T-019 screenshot).
  var EVENT_MAX_TIME = 180, EVENT_MAX_AVERAGE = 2, EVENT_OSCILLATION = 1, EVENT_LOW = 0, EVENT_HIGH = 100, EVENT_INVALID = 127;

  // The pulse-rate detector is the same code on the pulse series (SPO2_FORMAT.md §7.3):
  // valid range 0..254, probe-out 255, only falls count.
  var PULSE_HIGH = 254, PULSE_INVALID = 255;

  function detectEvents(spo2, drop, minTime, high, invalid) {
    if (high === undefined) high = EVENT_HIGH;
    if (invalid === undefined) invalid = EVENT_INVALID;
    var series = spo2.map(function (value) { return (value === null || value === undefined) ? invalid : value; });
    var candidates = [];
    var fallStart = 0, fallEnd = 0;
    function finish() {
      if (fallStart && fallEnd && fallEnd - fallStart > 0) candidates.push([fallStart, fallEnd, series[fallStart], series[fallEnd]]);
      fallStart = 0; fallEnd = 0;
    }
    for (var i = 0; i < series.length; i++) {
      var value = series[i];
      if (value > high || value < EVENT_LOW) { finish(); continue; }
      if (i === 0) continue;
      var previous = series[i - 1];
      if (value > previous) {
        finish();
      } else if (value === previous) {
        if (fallStart) fallEnd = i;
      } else if (fallStart) {
        fallEnd = i;
      } else if (previous > EVENT_LOW && previous < high) {
        fallStart = i - 1; fallEnd = i;
      }
    }
    finish();

    function accepted(candidate) {
      var duration = candidate[1] - candidate[0], depth = candidate[2] - candidate[3];
      if (!duration || depth < drop || duration < minTime || duration > EVENT_MAX_TIME) return false;
      if (!(Math.floor(depth / duration) < EVENT_MAX_AVERAGE)) return false;
      for (var k = candidate[0]; k <= candidate[1]; k++) { if (!(series[k] >= EVENT_LOW && series[k] <= high)) return false; }
      return true;
    }

    var events = [];
    if (!candidates.length) return events;
    var current = candidates[0].slice();
    for (var j = 1; j < candidates.length; j++) {
      var next = candidates[j];
      if (next[2] - current[3] <= EVENT_OSCILLATION && next[3] < current[3] && next[2] < current[2] && next[0] - current[1] <= minTime) {
        current[1] = next[1]; current[3] = next[3];
      } else {
        if (accepted(current)) events.push(current);
        current = next.slice();
      }
    }
    if (accepted(current)) events.push(current);
    return events.map(function (event) { return { start: event[0], nadir: event[1], from_percent: event[2], to_percent: event[3] }; });
  }

  // Python's round(x, n): nearest, exact ties to even (Math.round is half-up and
  // value * 100 is inexact). toFixed is exact; a tie is a value whose exact decimal
  // expansion is the kept digits, a 5 and nothing else.
  function pyRound(value, digits) {
    var fixedText = Math.abs(value).toFixed(digits + 40);
    var cutIndex = fixedText.length - 40;
    var roundedDown = Number(fixedText.slice(0, cutIndex)), roundedUp = Number(Math.abs(value).toFixed(digits));
    var result = roundedUp;
    if (fixedText.slice(cutIndex) === '5' + new Array(40).join('0') && Number(fixedText.slice(cutIndex - 1, cutIndex)) % 2 === 0) result = roundedDown;
    return value < 0 ? -result : result;
  }
  function round2(value) { return pyRound(value, 2); }
  function round1(value) { return pyRound(value, 1); }
  function sum(items, valueOf) { return items.reduce(function (total, item) { return total + valueOf(item); }, 0); }

  function summarizeEvents(spo2, events, criteria) {
    var valid = [];
    for (var i = 0; i < spo2.length; i++) {
      var value = spo2[i];
      if (value !== null && value !== undefined && value >= 1 && value <= 100) valid.push(i);
    }
    var out = { samples: spo2.length, valid_samples: valid.length, total_event: events.length };
    if (!spo2.length) return out;
    var hours = spo2.length / 3600.0;
    out.index_per_hour = round2(events.length / hours);
    out.adjusted_index_per_hour = valid.length ? round2(events.length / (valid.length / 3600.0)) : null;
    out.artifact_percent = round2(100.0 * (spo2.length - valid.length) / spo2.length);
    out.average_low_spo2 = events.length ? round2(sum(events, function (event) { return event.to_percent; }) / events.length) : null;
    var low = events.filter(function (event) { return event.to_percent < criteria; });
    out.events_below_criteria = low.length;
    out.average_low_spo2_below_criteria = low.length ? round2(sum(low, function (event) { return event.to_percent; }) / low.length) : null;
    // "Time (min) <criteria" (SPO2_FORMAT.md Sec7.1), same valid samples as the rest of
    // this report -- not a separately-filtered count (T-044).
    out.time_below_criteria_seconds = valid.filter(function (i) { return spo2[i] < criteria; }).length;
    out.average_event_duration_seconds = events.length ? round1(sum(events, function (event) { return event.nadir - event.start; }) / events.length) : null;
    var inside = {};
    events.forEach(function (event) { for (var k = event.start; k <= event.nadir; k++) inside[k] = true; });
    var basal = valid.filter(function (i) { return !inside[i]; }).map(function (i) { return spo2[i]; });
    out.basal_spo2 = basal.length ? round2(sum(basal, function (value) { return value; }) / basal.length) : null;
    return out;
  }

  // Pulse-channel report values, ported from desaturation.summarize_pulse (valid pulse 1..250).
  function summarizePulse(pulse, events) {
    var valid = 0;
    for (var i = 0; i < pulse.length; i++) {
      var value = pulse[i];
      if (value !== null && value !== undefined && value >= 1 && value <= 250) valid++;
    }
    var out = { samples: pulse.length, valid_samples: valid, total_event: events.length };
    if (!pulse.length) return out;
    out.index_per_hour = round2(events.length / (pulse.length / 3600.0));
    out.adjusted_index_per_hour = valid ? round2(events.length / (valid / 3600.0)) : null;
    out.artifact_percent = round2(100.0 * (pulse.length - valid) / pulse.length);
    out.average_event_duration_seconds = events.length ? round1(sum(events, function (event) { return event.nadir - event.start; }) / events.length) : null;
    return out;
  }
  // END desaturation-port

  function recomputeEvents() {
    var drop = parseFloat(document.getElementById('dropPercent').value);
    var minTime = parseInt(document.getElementById('minimumTime').value, 10);
    var criteria = parseFloat(document.getElementById('criteriaLevel').value);
    if (isNaN(drop) || drop < 1 || drop > 20) return;
    if (isNaN(minTime) || minTime < 1 || minTime > EVENT_MAX_TIME) return;
    if (isNaN(criteria) || criteria < 1 || criteria > 99) return;
    var events = detectEvents(spo2Series, drop, minTime);
    analysis.events = events;
    analysis.summary = summarizeEvents(spo2Series, events, criteria);
    analysis.parameters = { drop: drop, min_time: minTime, max_time: EVENT_MAX_TIME, criteria: criteria };
    stats(); render();
  }

  function recomputePulse() {
    var drop = parseFloat(document.getElementById('pulseDropBpm').value);
    var minTime = parseInt(document.getElementById('pulseMinimumTime').value, 10);
    if (isNaN(drop) || drop < 2 || drop > 20) return;
    if (isNaN(minTime) || minTime < 1 || minTime > EVENT_MAX_TIME) return;
    var events = detectEvents(pulseSeries, drop, minTime, PULSE_HIGH, PULSE_INVALID);
    analysis.pulse = {
      events: events,
      summary: summarizePulse(pulseSeries, events),
      parameters: { drop: drop, min_time: minTime },
    };
    stats(); render();
  }

  document.getElementById('dropPercent').value = analysis.parameters.drop;
  document.getElementById('minimumTime').value = analysis.parameters.min_time;
  document.getElementById('criteriaLevel').value = analysis.parameters.criteria;
  document.getElementById('pulseDropBpm').value = analysis.pulse.parameters.drop;
  document.getElementById('pulseMinimumTime').value = analysis.pulse.parameters.min_time;
  ['dropPercent', 'minimumTime', 'criteriaLevel'].forEach(function (id) {
    document.getElementById(id).addEventListener('input', recomputeEvents);
  });
  ['pulseDropBpm', 'pulseMinimumTime'].forEach(function (id) {
    document.getElementById(id).addEventListener('input', recomputePulse);
  });

  // Fixed ranges so different recordings are visually comparable, not
  // auto-scaled per file. SpO2 50-100% (below 50 is clamped, not expected
  // in practice); heart rate 30-220 bpm, a generic pulse-oximeter display
  // range covering rest through heavy exertion.
  var SPO2_LOW = 50, SPO2_HIGH = 100;
  var HEART_RATE_LOW = 30, HEART_RATE_HIGH = 220;
  var show = { spo2: true, heart_rate: true }; // per-channel switches (checkboxes in the legend)

  var canvas = document.getElementById('chart');
  var context = canvas.getContext('2d');
  var tooltip = document.getElementById('tooltip');
  var resetButton = document.getElementById('resetZoom');
  var paddingLeft = 50, paddingRight = 55, paddingTop = 20, paddingBottom = 34;

  // Zoom window: [viewStart, viewEnd] indices into `records`, inclusive.
  // Horizontal-only responsiveness: canvas width follows the container;
  // height is fixed (set via the height="420" attribute), never stretched.
  var viewStart = 0, viewEnd = recordCount - 1;
  var layout = null; // recomputed by render(): {cssWidth, plotWidth, plotHeight, paddingLeft, paddingTop, paddingBottom, xPosition, visibleStart, visibleEnd, count}

  function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }

  function formatTime(timestamp) {
    var separator = String(timestamp).indexOf('T');
    return separator === -1 ? String(timestamp) : String(timestamp).slice(separator + 1);
  }

  var CSS_HEIGHT = canvas.height; // fixed CSS height, read once; never changed by resize
                                   // (horizontal-only stretch) -- must not be re-read from
                                   // canvas.height after the first render, since that attribute
                                   // gets overwritten with the DPR-scaled pixel buffer size below.
  function render() {
    var cssWidth = canvas.parentElement.clientWidth;
    var cssHeight = CSS_HEIGHT;
    var pixelRatio = window.devicePixelRatio || 1;
    // Both the pixel buffer (canvas.width/height) and the CSS display size
    // must be set for a sharp, correctly-clipped render at any DPR -- scaling
    // only the width here previously left the buffer too short vertically,
    // silently clipping anything below CSS y ~= cssHeight / pixelRatio (the x-axis
    // time labels included).
    canvas.width = cssWidth * pixelRatio;
    canvas.height = cssHeight * pixelRatio;
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, cssWidth, cssHeight);

    var plotWidth = cssWidth - paddingLeft - paddingRight, plotHeight = cssHeight - paddingTop - paddingBottom;
    var visibleStart = viewStart, visibleEnd = viewEnd, count = visibleEnd - visibleStart + 1;

    function xPosition(index) { return paddingLeft + (count <= 1 ? 0 : ((index - visibleStart) / (count - 1)) * plotWidth); }
    function ySpo2(value) { return paddingTop + (1 - (clamp(value, SPO2_LOW, SPO2_HIGH) - SPO2_LOW) / (SPO2_HIGH - SPO2_LOW)) * plotHeight; }
    function yHeartRate(value) { return paddingTop + (1 - (clamp(value, HEART_RATE_LOW, HEART_RATE_HIGH) - HEART_RATE_LOW) / (HEART_RATE_HIGH - HEART_RATE_LOW)) * plotHeight; }

    layout = { cssWidth: cssWidth, plotWidth: plotWidth, plotHeight: plotHeight, paddingLeft: paddingLeft, paddingTop: paddingTop, paddingBottom: paddingBottom, xPosition: xPosition, visibleStart: visibleStart, visibleEnd: visibleEnd, count: count };

    // Axes
    context.strokeStyle = '#ccc';
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(paddingLeft, paddingTop); context.lineTo(paddingLeft, paddingTop + plotHeight); context.lineTo(paddingLeft + plotWidth, paddingTop + plotHeight);
    context.stroke();

    // Horizontal gridlines + SpO2 labels (left)
    context.font = '11px sans-serif';
    context.strokeStyle = '#eee';
    context.fillStyle = '#2b6cb0';
    for (var spo2Tick = SPO2_LOW; spo2Tick <= SPO2_HIGH; spo2Tick += 10) {
      var spo2TickY = ySpo2(spo2Tick);
      context.beginPath(); context.moveTo(paddingLeft, spo2TickY); context.lineTo(paddingLeft + plotWidth, spo2TickY); context.stroke();
      if (show.spo2) context.fillText(spo2Tick + '%', 4, spo2TickY + 4);
    }

    // Heart-rate labels (right), skipping any that would overlap
    context.fillStyle = '#c05621';
    var lastLabelY = null;
    for (var heartRateTick = HEART_RATE_LOW; show.heart_rate && heartRateTick <= HEART_RATE_HIGH; heartRateTick += 40) {
      var heartRateTickY = yHeartRate(heartRateTick);
      if (lastLabelY !== null && Math.abs(heartRateTickY - lastLabelY) < 14) continue;
      context.fillText(Math.round(heartRateTick) + '', paddingLeft + plotWidth + 6, heartRateTickY + 4);
      lastLabelY = heartRateTickY;
    }

    // X-axis time ticks: ~6 evenly spaced across the visible range
    var tickCount = Math.min(6, count);
    context.fillStyle = '#666';
    context.textAlign = 'center';
    for (var tick = 0; tick < tickCount; tick++) {
      var tickIndex = visibleStart + Math.round((tick / Math.max(1, tickCount - 1)) * (count - 1));
      var tickX = xPosition(tickIndex);
      context.strokeStyle = '#f2f2f2';
      context.beginPath(); context.moveTo(tickX, paddingTop); context.lineTo(tickX, paddingTop + plotHeight); context.stroke();
      context.fillText(formatTime(records[tickIndex].timestamp), tickX, paddingTop + plotHeight + 16);
    }
    context.textAlign = 'left';

    function drawSeries(key, color, yPosition) {
      context.strokeStyle = color;
      context.lineWidth = 1.5;
      context.beginPath();
      var drawing = false;
      for (var i = visibleStart; i <= visibleEnd; i++) {
        var value = records[i][key];
        if (value === null || value === undefined) { drawing = false; continue; }
        var pointX = xPosition(i), pointY = yPosition(value);
        if (!drawing) { context.moveTo(pointX, pointY); drawing = true; } else { context.lineTo(pointX, pointY); }
      }
      context.stroke();
    }

    // Desaturation events (SpO2 Assistant's method): shaded from the start of the fall to the nadir.
    if (show.spo2) {
      context.fillStyle = 'rgba(197,48,48,0.18)';
      analysis.events.forEach(function (event) {
        if (event.nadir < visibleStart || event.start > visibleEnd) return;
        var bandStart = xPosition(Math.max(event.start, visibleStart)), bandEnd = xPosition(Math.min(event.nadir, visibleEnd));
        context.fillRect(bandStart, paddingTop, Math.max(2, bandEnd - bandStart), plotHeight);
      });
    }

    // Pulse-rate events (falls only): amber bands, drawn with the heart-rate series.
    if (show.heart_rate) {
      context.fillStyle = 'rgba(214,158,46,0.28)';
      analysis.pulse.events.forEach(function (event) {
        if (event.nadir < visibleStart || event.start > visibleEnd) return;
        var bandStart = xPosition(Math.max(event.start, visibleStart)), bandEnd = xPosition(Math.min(event.nadir, visibleEnd));
        context.fillRect(bandStart, paddingTop, Math.max(2, bandEnd - bandStart), plotHeight);
      });
    }

    if (show.spo2) drawSeries('spo2', '#2b6cb0', ySpo2);
    if (show.heart_rate) drawSeries('heart_rate', '#c05621', yHeartRate);

    resetButton.style.display = (visibleStart === 0 && visibleEnd === recordCount - 1) ? 'none' : 'inline';
  }

  function nearestIndex(mouseX) {
    if (!layout) return null;
    var fraction = clamp((mouseX - layout.paddingLeft) / layout.plotWidth, 0, 1);
    return clamp(layout.visibleStart + Math.round(fraction * (layout.count - 1)), layout.visibleStart, layout.visibleEnd);
  }

  // Hover tooltip: shows the exact reading at the nearest point.
  canvas.addEventListener('mousemove', function (mouseEvent) {
    if (dragStartX !== null) { handleDrag(mouseEvent); return; }
    var rect = canvas.getBoundingClientRect();
    var pointerX = mouseEvent.clientX - rect.left;
    var index = nearestIndex(pointerX);
    if (index === null) return;
    var record = records[index];
    tooltip.style.display = 'block';
    tooltip.style.left = (pointerX + 12) + 'px';
    tooltip.style.top = (mouseEvent.clientY - rect.top - 10) + 'px';
    tooltip.innerHTML = formatTime(record.timestamp) +
      (show.spo2 ? '<br>SpO2: ' + (record.spo2 === null ? '--' : record.spo2 + '%') : '') +
      (show.heart_rate ? '<br>HR: ' + (record.heart_rate === null ? '--' : record.heart_rate + ' bpm') : '');
  });
  canvas.addEventListener('mouseleave', function () { tooltip.style.display = 'none'; });

  // Click-drag to zoom into a horizontal range; reset link restores the full view.
  var dragStartX = null, dragStartIndex = null;
  var selectionDiv = document.createElement('div');
  selectionDiv.style.cssText = 'position:absolute;top:0;bottom:0;background:rgba(43,108,176,0.12);border-left:1px solid #2b6cb0;border-right:1px solid #2b6cb0;display:none;pointer-events:none;';
  document.getElementById('chartWrapper').appendChild(selectionDiv);

  canvas.addEventListener('mousedown', function (mouseEvent) {
    var rect = canvas.getBoundingClientRect();
    dragStartX = mouseEvent.clientX - rect.left;
    dragStartIndex = nearestIndex(dragStartX);
    selectionDiv.style.display = 'block';
    selectionDiv.style.left = dragStartX + 'px';
    selectionDiv.style.width = '0px';
  });

  function handleDrag(mouseEvent) {
    var rect = canvas.getBoundingClientRect();
    var pointerX = mouseEvent.clientX - rect.left;
    var left = Math.min(dragStartX, pointerX), width = Math.abs(pointerX - dragStartX);
    selectionDiv.style.left = left + 'px';
    selectionDiv.style.width = width + 'px';
  }

  window.addEventListener('mouseup', function (mouseEvent) {
    if (dragStartX === null) return;
    var rect = canvas.getBoundingClientRect();
    var pointerX = clamp(mouseEvent.clientX - rect.left, 0, rect.width);
    var endIndex = nearestIndex(pointerX);
    selectionDiv.style.display = 'none';
    var dragged = Math.abs(pointerX - dragStartX) > 6; // ignore accidental tiny drags (treat as a click)
    dragStartX = null;
    if (dragged && endIndex !== null && dragStartIndex !== null && endIndex !== dragStartIndex) {
      viewStart = Math.min(dragStartIndex, endIndex);
      viewEnd = Math.max(dragStartIndex, endIndex);
      render();
    }
  });

  resetButton.addEventListener('click', function () {
    viewStart = 0; viewEnd = recordCount - 1;
    render();
  });

  window.addEventListener('resize', render); // horizontal-only: render() keeps height fixed

  // Session statistics, computed over the whole recording regardless of zoom.
  function stats() {
    var spo2Readings = records.map(function (record) { return record.spo2; }).filter(function (value) { return value !== null && value !== undefined; });
    var heartRateReadings = records.map(function (record) { return record.heart_rate; }).filter(function (value) { return value !== null && value !== undefined; });
    var summary = analysis.summary;
    function average(values) { return values.length ? (values.reduce(function (total, value) { return total + value; }, 0) / values.length) : null; }
    // "No-signal / probe-out" and the Time-below-criteria row below both come from
    // analysis.summary (desaturation-port), so they use the same 1..100 valid-sample
    // definition as every other report value instead of each filtering on its own (T-044).
    var rows = [
      ['__group__', 'Recording'],
      ['Duration', formatSeconds(recordCount) + ' (' + recordCount + ' records)'],
      ['SpO2 min / avg / max', spo2Readings.length ? Math.min.apply(null, spo2Readings) + '% / ' + average(spo2Readings).toFixed(1) + '% / ' + Math.max.apply(null, spo2Readings) + '%' : 'n/a'],
      ['Heart rate min / avg / max', heartRateReadings.length ? Math.min.apply(null, heartRateReadings) + ' / ' + average(heartRateReadings).toFixed(1) + ' / ' + Math.max.apply(null, heartRateReadings) + ' bpm' : 'n/a'],
      ['No-signal / probe-out', formatSeconds(recordCount - summary.valid_samples) + ' (' + summary.artifact_percent.toFixed(1) + '%)'],
    ];
    function formatOneDecimal(value, unit) { return value === null || value === undefined ? 'n/a' : value.toFixed(1) + unit; }
    rows.push(
      ['__group__', 'Desaturation analysis'],
      ['Event index', formatOneDecimal(summary.index_per_hour, ' /hr') + ' (adjusted ' + formatOneDecimal(summary.adjusted_index_per_hour, ' /hr') + ')'],
      ['Desaturation events', summary.total_event + ' (red bands; fall of at least ' + analysis.parameters.drop + '% over ' + analysis.parameters.min_time + '-' + analysis.parameters.max_time + ' s)'],
      ['Events below ' + analysis.parameters.criteria + '%', summary.events_below_criteria + (summary.average_low_spo2_below_criteria === null ? '' : ' (average low ' + formatOneDecimal(summary.average_low_spo2_below_criteria, '%') + ')')],
      ['Average lowest SpO2 of events', formatOneDecimal(summary.average_low_spo2, '%')],
      ['Basal SpO2', formatOneDecimal(summary.basal_spo2, '%') + ' (mean outside the event falls, as SpO2 Assistant computes it)'],
      ['Time below ' + analysis.parameters.criteria + '% SpO2', formatSeconds(summary.time_below_criteria_seconds) + (summary.valid_samples ? ' (' + (100 * summary.time_below_criteria_seconds / summary.valid_samples).toFixed(1) + '% of valid readings)' : '')]
    );
    var pulseSummary = analysis.pulse.summary, pulseParameters = analysis.pulse.parameters;
    rows.push(
      ['__group__', 'Pulse-rate events'],
      ['Event index', formatOneDecimal(pulseSummary.index_per_hour, ' /hr') + ' (adjusted ' + formatOneDecimal(pulseSummary.adjusted_index_per_hour, ' /hr') + ')'],
      ['Pulse-rate events', pulseSummary.total_event + ' (amber bands; fall of at least ' + pulseParameters.drop + ' bpm over ' + pulseParameters.min_time + '-' + analysis.parameters.max_time + ' s)'],
      ['Average event duration', formatOneDecimal(pulseSummary.average_event_duration_seconds, ' s')]
    );
    var table = document.getElementById('stats');
    table.innerHTML = rows.map(function (row) {
      if (row[0] === '__group__') return '<tr><th colspan="2" class="statsGroup">' + row[1] + '</th></tr>';
      return '<tr><th>' + row[0] + '</th><td>' + row[1] + '</td></tr>';
    }).join('');
  }

  document.getElementById('showSpo2').addEventListener('change', function (changeEvent) {
    show.spo2 = changeEvent.target.checked; render();
  });
  document.getElementById('showHeartRate').addEventListener('change', function (changeEvent) {
    show.heart_rate = changeEvent.target.checked; render();
  });
  // Print uses the browser's own dialog; the canvas is redrawn at the print
  // width first (see the @media print rules above).
  document.getElementById('printButton').addEventListener('click', function () { window.print(); });
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
            "timestamp": record.get("timestamp"),
            "spo2": record.get("spo2"),
            "heart_rate": record.get("heart_rate"),
            "flags": record.get("flags"),
        }
        for record in records
    ]
    data_json = json.dumps(payload).replace("<", "\\u003c")
    spo2 = [point["spo2"] for point in payload]
    events = desaturation.detect_events(spo2)
    pulse = [point["heart_rate"] for point in payload]
    pulse_events = desaturation.detect_pulse_events(pulse)
    analysis = {
        "events": events,
        "summary": desaturation.summarize(spo2, events),
        "parameters": {
            "drop": desaturation.DROP,
            "min_time": desaturation.MIN_TIME,
            "max_time": desaturation.MAX_TIME,
            "criteria": desaturation.CRITERIA,
        },
        "pulse": {
            "events": pulse_events,
            "summary": desaturation.summarize_pulse(pulse, pulse_events),
            "parameters": {"drop": desaturation.PULSE_DROP, "min_time": desaturation.PULSE_MIN_TIME},
        },
    }
    events_json = json.dumps(analysis).replace("<", "\\u003c")
    return _TEMPLATE.replace("%%DATA%%", data_json).replace("%%EVENTS%%", events_json)
