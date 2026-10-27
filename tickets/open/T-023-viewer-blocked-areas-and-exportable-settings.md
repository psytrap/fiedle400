# T-023: Viewer area-exclusion selection

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (chart, drag-select already used for zoom)
  - `fiedle400/desaturation.py` (event detection / `summarize()` -- whether
    exclusion feeds into these or is display-only)
  - `tickets/done/2026-W43/T-007-html-viewer-feature-evaluation.md` (item 14,
    "Hide or exclude part of the data" -- previously **Skip**)
  - `tickets/open/T-024-viewer-settings-export-and-adjustable-parameters.md`
    (split off from this ticket -- persisting the exclusion state this
    ticket creates, and making analysis parameters adjustable)

---

## Description & Context

psytrap: let the viewer mark blocked/excluded regions on the chart (click
or drag-select, similar to the existing zoom drag).

**Split 2026-10-20** from a combined ticket that also asked for an
export/save button and adjustable analysis parameters -- those are now
**T-024**, since they're a separable persistence/configuration concern from
the selection interaction itself. This ticket is just the selection
mechanism and what it means for the chart and (possibly) the analysis.

**This revisits, but does not simply overturn, T-007's item 14 verdict.**
T-007 marked excluding data **Skip** with the reasoning "a viewer that
edits what it shows is the wrong default for medical-looking data." That
concern was about silently changing what the chart displays as if it were
the recording. This request is narrower and different in kind: it's about
the viewer's own **analysis configuration** (which stretches to exclude
from statistics/event detection) being something the user can set --
not editing or hiding the underlying `.spo2` file, which stays untouched on
disk either way. Any implementation should keep that distinction explicit
(e.g. excluded ranges show as a clearly marked overlay, never silently
vanish from the chart) so it doesn't become the thing T-007 was right to
avoid.

**Not decided here, for whoever picks this up:**
- Whether excluded ranges affect `desaturation.py`'s event detection and
  `summarize()` (basal SpO2, index, etc.), or are display-only -- affects
  whether this also touches `fiedle400/desaturation.py`'s functions or stays
  purely in the JS/template layer.
- Interaction with T-024: this ticket's exclusion state is what T-024 would
  persist, so the in-page data structure for "excluded ranges" should be
  designed with that in mind even though saving it is out of this ticket's
  own scope.

---

## Criteria

- [ ] Scope above decided with psytrap and this ticket updated before
      implementation starts (same pattern as T-018's own placeholder
      phase).
- [ ] Click/drag area-exclusion selection in the chart, visually distinct
      from the existing red desaturation-event bands and from plain
      "no signal" stretches (gray, per the gap-marking work around T-022).
- [ ] Excluded ranges are clearly marked as excluded, never silently
      removed from the chart -- keeps this distinct from T-007 item 14's
      "wrong default" concern.
- [ ] Decided and documented: does exclusion affect `desaturation.py`'s event
      detection/summary, or is it display-only for this ticket (with
      analysis-affecting exclusion as a possible later extension)?
- [ ] A test covering the exclusion state (selection, visual marking, and
      whichever analysis effect was decided) that fails without the change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
