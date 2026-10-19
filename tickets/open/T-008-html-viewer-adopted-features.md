# T-008: HTML viewer extras adopted from the T-007 evaluation

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the T-005 viewer)
  - `tests/` for whatever is testable without a browser

---

## Description & Context

Follow-up from [T-007](../done/T-007-html-viewer-feature-evaluation.md). The
evaluation compared the viewer with SpO2 Assistant's own feature labels (strings in
`archive/bruteforce/SpO2.exe`) and adopted four items, against the viewer as of
**v0.4.12**. T-006 (remove `plot`) waits on this ticket for parity.

**Update (psytrap + local, 2026-10-19): two of the four adopted items shipped
independently in v0.4.13**, in direct response to "this looks like a basic
draft" feedback on T-005, before this ticket was read. Reconciled below
rather than silently left stale.

1. **SpO2 and pulse trace with a switch per channel** (vendor:
   `BTN_Spo2GraphEnable`, `BTN_PRGraphEnable`). **Still open.** Not built.
2. **Choose the time window, with zoom and pan.** **Done in v0.4.13**
   (`fiedle400/spo2_viewer.py`, commit `a035529`) -- click-drag to zoom into
   a range, a "Reset zoom" link to restore the full view. Built as free
   drag-select zoom rather than the vendor's fixed "Time Interval" dropdown;
   functionally a superset (any range, not just preset windows). Verified
   working via real simulated mouse events over CDP (mousedown/mousemove/
   mouseup), not just visual inspection.
3. **Summary numbers: minimum and average SpO2, average and lowest pulse,
   time below a chosen level.** **Done in v0.4.13**, close to spec: SpO2
   min/avg/max and heart-rate min/avg/max (vendor shows avg/lowest pulse,
   not max -- max was included anyway since it's the same computation and
   arguably as useful), plus "time below 90% SpO2" (vendor: a
   *user-chosen* level via `STR_TimeLessThan`; v0.4.13 hardcodes 90%, the
   common clinical desaturation threshold, not a selector). **Gap vs. the
   vendor spec, left for this ticket:** make the 90% threshold configurable
   rather than fixed, if that's still wanted now that the fixed version
   exists.
4. **Print** with the browser's own print and a print stylesheet. **Still
   open.** Not built.

**Precondition verified, not just assumed:** records at the sentinel values
(SpO2 127, pulse 255; see `SPO2_FORMAT.md`) are probe-out, never readings,
and must not be drawn as data or counted in any statistic. Checked directly
against `fiedle400/engine/detector.py` (lines ~194-205, 2026-10-19): a
decoded record only gets a non-`None` `spo2`/`heart_rate` value when the
raw reading is in range (`valid = 0 < v1 <= limit and 0 < v2 <= limit`);
out-of-range readings stay `None` all the way from the decoder through
`export.py` to `spo2_viewer.py`. **fiedle400 never hands the viewer a
literal 127/255 as a number** -- the precondition was already satisfied by
the existing pipeline before this ticket, not something it needs to add.
v0.4.13's stats (`stats()` in `spo2_viewer.py`) and line-drawing
(`drawSeries`) both already filter on `!== null`, consistent with this. No
real finger-out recording exists yet to test against (T1); this remains
verified against the decoder's logic and synthetic records only, not a
real capture.

Not adopted, with reasons: see the table in T-007 (events and index, distributions, alarm
lines, smoothing and image export are deferred; file exports, side-by-side, editing, patient
data, live view, PI and colour/language are skipped).

---

## Criteria

- [x] Sentinel records are neither plotted nor counted in any statistic --
      verified against `detector.py`'s decode logic directly (see above),
      not just by inspecting the viewer's own filtering.
- [ ] Per-channel switch and print work (the two still-open items).
- [x] Time-window selection with zoom/pan, and summary numbers, work --
      shipped in v0.4.13. Decide whether the desaturation threshold should
      become user-configurable (vendor has it as a chosen level; v0.4.13
      hardcodes 90%) as part of finishing this ticket, or is fine fixed.
- [ ] Summary numbers are plain arithmetic on the samples; no clinical
      index is shown -- true for what shipped (min/avg/max, time below a
      threshold), re-confirm once the remaining items are added.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
