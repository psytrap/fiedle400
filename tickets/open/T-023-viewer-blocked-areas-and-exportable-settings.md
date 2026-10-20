# T-023: Viewer area-exclusion selection with an export/save settings button

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (chart, drag-select already used for zoom,
    the statistics panel, `desat.py` params wiring)
  - `fiedle400/desat.py` (`DROP`/`MIN_TIME`/`CRITERIA` -- currently fixed
    constants, not exposed in the page)
  - `tickets/done/2026-W43/T-007-html-viewer-feature-evaluation.md` (item 14,
    "Hide or exclude part of the data" -- previously **Skip**)
  - `tickets/done/2026-W43/T-018-desaturation-events-and-basal-spo2.md`
    ("Not done: changing the parameters in the page")

---

## Description & Context

psytrap: let the viewer mark blocked/excluded regions on the chart (click
or drag-select, similar to the existing zoom drag), and add an export/save
button so the user can keep their configured settings -- the excluded
ranges plus any analysis limits/thresholds they've set (desaturation drop
%, minimum duration, criteria level) -- rather than losing them every time
the page is a fresh one-shot temp file (T-005's own design: generate, open,
clean up).

**This revisits, but does not simply overturn, T-007's item 14 verdict.**
T-007 marked excluding data **Skip** with the reasoning "a viewer that
edits what it shows is the wrong default for medical-looking data." That
concern was about silently changing what the chart displays as if it were
the recording. This request is narrower and different in kind: it's about
the viewer's own **analysis configuration** (which stretches to exclude
from statistics/event detection, and what thresholds to use) being
something the user can set and keep -- not editing or hiding the
underlying `.spo2` file, which stays untouched on disk either way. Any
implementation should keep that distinction explicit (e.g. excluded ranges
show as a clearly marked overlay, never silently vanish from the chart) so
it doesn't become the thing T-007 was right to avoid.

**Also pulls in T-018's own leftover item.** T-018 shipped `desat.py` with
fixed constants (`DROP=4`, `MIN_TIME=10`, `CRITERIA=88`) and explicitly
left "changing the parameters in the page" as not done. A settings
export/save feature is the natural place to also make those adjustable in
the UI, rather than solving area-exclusion and parameter-configuration as
two separate, inconsistent features later.

**Not decided here, for whoever picks this up:**
- What "export/save" actually means for a one-shot temp-file page (T-005):
  download a small JSON settings file the user keeps and could reload into
  a later viewer session? Browser `localStorage` tied to the recording's
  identity? Something else -- this needs a concrete mechanism, not just
  the request.
- Whether excluded ranges affect `desat.py`'s event detection and
  `summarize()` (basal SpO2, index, etc.), or are display-only -- affects
  whether this also touches `fiedle400/desat.py`'s functions or stays
  purely in the JS/template layer.
- Whether reloading a saved settings file into a *different* recording
  (not the one it was made for) should be allowed, warned about, or
  rejected.

---

## Criteria

- [ ] Scope above decided with psytrap and this ticket updated before
      implementation starts (same pattern as T-018's own placeholder
      phase).
- [ ] Click/drag area-exclusion selection in the chart, visually distinct
      from the existing red desaturation-event bands and from plain
      "no signal" stretches (gray, per the gap-marking work around T-022).
- [ ] Desaturation parameters (drop %, min duration, criteria level)
      adjustable in the page, not just the fixed `desat.py` constants.
- [ ] An export/save action that persists both the excluded ranges and the
      configured parameters in a concrete, chosen format.
- [ ] Excluded ranges are clearly marked as excluded, never silently
      removed from the chart -- keeps this distinct from T-007 item 14's
      "wrong default" concern.
- [ ] A test per piece (exclusion state, parameter adjustment, export
      format) that fails without the change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
