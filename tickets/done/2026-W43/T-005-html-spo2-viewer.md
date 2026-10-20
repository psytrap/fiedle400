# T-005: HTML viewer for `.spo2` files, offered from the wizard

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud (no hardware involved; pure software/UI work)
- **Scope & Relevant Files:**
  - A new HTML file/template able to read and render a `.spo2` file
    (location TBD -- a static page shipped with the tool, or generated
    per-export)
  - `fiedle400/cli.py` (`run_interactive_wizard`'s download flow)
  - `tests/test_cli_interactive.py`

---

## Description & Context

psytrap: "have a html in fiedle400 that can read spo2. Lets have a
step in the wizard that asks for opening spo2 when extracting spo2
that defaults to no."

No HTML viewer exists in the project today (checked: the only `.html`
in the repo is a build-tool xref artifact, unrelated).

The wizard already has a precedent for exactly this shape of prompt --
after rendering a PNG plot it asks `"Open the plot now? [Y/n]"`
(default **yes**, `fiedle400/cli.py` around line 896, `_open_in_viewer`
for the OS-native opener). This ticket is the same idea, but:
- for the raw `.spo2` **data** export (not the PNG plot path), via a
  **new HTML page** this project doesn't have yet, not the OS's native
  file opener;
- **defaulting to no**, the opposite of the PNG prompt's default --
  psytrap's request was explicit about this, presumably because
  opening a browser is heavier/more intrusive than opening an image
  viewer, or because the HTML viewer is new/unproven.

## Decided (psytrap, 2026-10-19, discussed before execution)

**Static, not generated-per-export.** One HTML file bundled with the
tool (consistent with the zero-extra-dependency philosophy for the
non-plot commands), not a fresh file written out per download. The
wizard opens this bundled page and points it at the specific `.spo2`
file just downloaded -- "po400 wizard opens bundled static html +
dynamic spo2."

**Resolved, 2026-10-19: inject the data at open-time, don't fetch it.**
Browsers (Chrome especially) block a `file://` page from reading
*other* local files via `fetch`/XHR for security reasons, so passing
the `.spo2` path in a URL and having the page load it itself would not
work reliably. psytrap asked whether the data could instead be
**injected during the open process** -- yes, and it's the better
mechanism, not just a workaround:

- One **template** is the bundled static asset -- the chart/CSS/JS,
  maintained once, containing a placeholder
  (`<script id="spo2-data" type="application/json">{{DATA}}</script>`).
- At open time, `fiedle400` reads the template, substitutes the
  specific recording's decoded records in as inline JSON, writes the
  result to a temp file (`tempfile.NamedTemporaryFile(suffix=".html")`),
  and opens *that* via `_open_in_viewer`.
- The browser never fetches anything -- the data is already embedded
  in the page before it's opened, so the `file://` restriction never
  applies. Works unconditionally, in every browser. No file-picker
  fallback needed at all; drop that from scope.

So "static" = the template (one file, one place to maintain the chart
code); "dynamic" = the per-open injection step, which is what makes
each opened page show the right recording. `fiedle400`'s own Python
side does the data decoding (reusing the existing `.spo2`/engine
decode path, not a client-side binary-format reimplementation in JS)
and hands the template already-decoded JSON -- simpler than parsing
the binary format twice (once in Python, once in JS) for no benefit.

The `plot`/matplotlib relationship is still open (see T-006 -- `plot`
removal is explicitly blocked on this reaching parity, so this viewer
does need to actually chart SpO2 + heart-rate, not just dump raw
bytes).

**Decided, 2026-10-19:**
- **Template storage: a Python string constant, for now.** Avoids any
  resource-path resolution complexity across platforms. psytrap: may
  be re-evaluated later (e.g. if the template grows large enough that
  a separate bundled file becomes worth the packaging complexity).
- **Temp-file lifecycle: cleaned up after the browser's had a chance
  to load it**, not left on disk. The deeper design of this (exact
  cleanup timing/mechanism, and whether the HTML approach stays a
  one-shot temp file at all once this becomes a standing feature) is
  deferred to T-007 -- see the note added there, not re-litigated here.

---

## Criteria

- [x] One static HTML template (bundled, maintained once) exists; a
      per-open step injects the specific recording's decoded data into
      a copy of it, with no client-side `fetch`/XHR of another file.
- [x] Wizard's download flow, when the chosen format is `spo2`, asks
      "Open it now? [y/N]" -- **default no**, opposite of the existing
      PNG-open prompt's default yes.
- [x] Reuses `_open_in_viewer` (or equivalent) rather than a new
      OS-dispatch mechanism.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**`fiedle400/spo2_viewer.py`** (new): `_TEMPLATE` is the bundled static
asset -- a Python string constant per the "constant for now" decision,
not a PyInstaller resource. It's a self-contained HTML page: inline
CSS, a vanilla-JS `<canvas>` dual-axis line chart (SpO2 % fixed 0-100
on the left, heart rate auto-scaled with a margin on the right), no
CDN, no external script tags. `build_viewer_html(records)` keeps only
the four fields the template uses (`timestamp`, `spo2`, `heart_rate`,
`flags` -- dropping anything else a caller's dict might carry, e.g.
`session_id`), serializes to JSON, escapes `<` as `<` so no field
could ever prematurely close the `<script>` tag it's embedded in
(defensive -- no real field does this today), and substitutes it into
the template's `%%DATA%%` placeholder.

**`fiedle400/cli.py`**: `_open_spo2_viewer(records, saved_path)` writes
the built HTML to a `tempfile.mkstemp(suffix=".html")` file, opens it
via the existing `_open_in_viewer` (same OS-native opener the PNG path
already uses), sleeps 2s to give the browser a moment to read the file,
then removes it -- the "cleaned up after the browser's had a chance to
load it" decision. If `_open_in_viewer` fails, the temp file is still
removed but `saved_path` (the real, already-saved `.spo2` file) is
printed instead, so nothing is ever lost. Wired into the wizard's
non-png save branch: `if save_fmt == "spo2": ...` prompts "Open it in
the HTML viewer now? [y/N]" (default no, per psytrap's explicit
request -- the opposite of the PNG path's default yes).

**Visually verified**, not just unit-tested: generated real HTML from
`build_viewer_html` with a 120-record synthetic recording including a
10-record probe-out gap, served it over a local HTTP server (direct
`file://` opens in this environment's browser tool render as inert
static snapshots, so a real server was needed to execute the chart's
JS), and screenshotted it. Confirmed: both SpO2 and heart-rate lines
draw correctly, the probe-out gap correctly breaks both lines rather
than interpolating across it, and the legend/title/record-count-and-
timespan header all render as intended. Fixed one real bug found this
way: the heart-rate axis's three labels (low/mid/high) could render on
top of each other when the data's range was narrow -- added a 14px
minimum-separation check that skips a label too close to the previous
one, then re-verified.

**Tests:** `tests/test_spo2_viewer.py` (4 tests, pure-function:
JSON injection, field filtering, the `<` escaping, empty-recording
handling) and 3 new tests in `tests/test_cli_interactive.py` (prompt
declined by default, accepted opens and cleans up the temp file,
opener-failure fallback names the real saved path). Four pre-existing
wizard tests needed an extra input in their `side_effect` sequences
since the new prompt now sits between the filename and erase steps for
any spo2-format download -- not logic changes, just accounting for the
new step. 280 tests total, OK (skipped=7).

**Not done, deferred per the ticket's own scope:** `T-006` (removing
`fiedle400 plot`) stays blocked until this reaches feature parity with
the matplotlib PNG -- it doesn't yet (no zoom/pan, no session
statistics); `T-007` holds the evaluation of what else to add, now
that there's a real viewer to evaluate against.
