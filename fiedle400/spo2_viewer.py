"""Self-contained HTML viewer for a decoded SpO2/pulse recording.

One static template (this module's _TEMPLATE constant) with the specific
recording's records injected as inline JSON at build time -- the page never
fetches anything else, so it works from a plain file:// open in any browser
with no server and no extra dependency (T-005).
"""

import json

_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>fiedle400 recording</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2em; background: #fafafa; color: #222; }
  h1 { font-size: 1.1em; margin-bottom: 0.2em; }
  #meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
  #legend { margin-bottom: 0.5em; font-size: 0.9em; }
  #legend span { margin-right: 1.5em; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.4em; }
  canvas { background: #fff; border: 1px solid #ddd; }
</style>
</head>
<body>
<h1>fiedle400 recording</h1>
<div id="meta"></div>
<div id="legend">
  <span><span class="dot" style="background:#2b6cb0"></span>SpO2 (%)</span>
  <span><span class="dot" style="background:#c05621"></span>Heart rate (bpm)</span>
</div>
<canvas id="c" width="1100" height="420"></canvas>
<script id="spo2-data" type="application/json">%%DATA%%</script>
<script>
(function () {
  var records = JSON.parse(document.getElementById('spo2-data').textContent);
  var meta = document.getElementById('meta');
  var n = records.length;
  if (n === 0) {
    meta.textContent = 'No records in this recording.';
    return;
  }
  meta.textContent = n + ' record(s), ' + records[0].timestamp + ' to ' + records[n - 1].timestamp;

  var canvas = document.getElementById('c');
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  var padL = 50, padR = 50, padT = 20, padB = 30;
  var plotW = W - padL - padR, plotH = H - padT - padB;

  function x(i) { return padL + (n <= 1 ? 0 : (i / (n - 1)) * plotW); }
  // SpO2 fixed 0-100%; heart rate auto-scaled with a small margin.
  var hrVals = records.map(function (r) { return r.heart_rate; }).filter(function (v) { return v !== null && v !== undefined; });
  var hrMin = hrVals.length ? Math.min.apply(null, hrVals) : 0;
  var hrMax = hrVals.length ? Math.max.apply(null, hrVals) : 200;
  var hrLo = Math.max(0, hrMin - 10), hrHi = hrMax + 10;

  function ySpo2(v) { return padT + (1 - v / 100) * plotH; }
  function yHr(v) { return padT + (1 - (v - hrLo) / (hrHi - hrLo)) * plotH; }

  // Axes
  ctx.strokeStyle = '#ccc';
  ctx.beginPath();
  ctx.moveTo(padL, padT); ctx.lineTo(padL, padT + plotH); ctx.lineTo(padL + plotW, padT + plotH);
  ctx.stroke();

  // SpO2 axis labels (left, fixed 0/50/100)
  ctx.fillStyle = '#2b6cb0';
  ctx.font = '11px sans-serif';
  [0, 50, 100].forEach(function (v) {
    var yy = ySpo2(v);
    ctx.fillText(v + '%', 4, yy + 4);
  });

  // Heart-rate axis labels (right) -- skip a label that would overlap the
  // previous one when the data range is narrow enough to crowd all three.
  ctx.fillStyle = '#c05621';
  var lastLabelY = null;
  [hrLo, (hrLo + hrHi) / 2, hrHi].forEach(function (v) {
    var yy = yHr(v);
    if (lastLabelY !== null && Math.abs(yy - lastLabelY) < 14) return;
    ctx.fillText(Math.round(v) + '', W - padR + 6, yy + 4);
    lastLabelY = yy;
  });

  function drawSeries(key, color, yFn) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    var drawing = false;
    for (var i = 0; i < n; i++) {
      var v = records[i][key];
      if (v === null || v === undefined) {
        drawing = false;
        continue;
      }
      var px = x(i), py = yFn(v);
      if (!drawing) {
        ctx.moveTo(px, py);
        drawing = true;
      } else {
        ctx.lineTo(px, py);
      }
    }
    ctx.stroke();
  }

  drawSeries('spo2', '#2b6cb0', ySpo2);
  drawSeries('heart_rate', '#c05621', yHr);
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
    return _TEMPLATE.replace("%%DATA%%", data_json)
