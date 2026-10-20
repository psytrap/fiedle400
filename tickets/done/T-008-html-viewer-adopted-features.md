# T-008: HTML viewer extras adopted from the T-007 evaluation

- **Status:** Done
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
   `BTN_Spo2GraphEnable`, `BTN_PRGraphEnable`). **Done in v0.4.18** (see
   Execution Notes).
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
   vendor spec:** the 90% level was fixed. **Closed in v0.4.18:** it is now
   a number field (50 to 99, default 90).
4. **Print** with the browser's own print and a print stylesheet. **Done in
   v0.4.18.**

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
- [x] Per-channel switch and print work (v0.4.18).
- [x] Time-window selection with zoom/pan, and summary numbers, work --
      shipped in v0.4.13. The desaturation level became user-configurable
      in v0.4.18 (default still 90%).
- [x] Summary numbers are plain arithmetic on the samples; no clinical
      index is shown -- re-confirmed after the v0.4.18 additions (min/avg/max,
      time below a level, probe-out share).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

**Added, 2026-10-19 (psytrap): T-007's evaluation only read `SpO2.exe`'s
strings, never the vendor's own PDF manual.** Found and read it
(`manual.pulseoximeter.org/SPO2_Assistant_Manual.pdf`, "CONTEC SpO2
Assistant User Manual", 2010-05-27, 26 pages) -- not previously checked.
Two concrete corrections to T-007's reasoning, not just new trivia:

- **Item 5 (desaturation events/index), marked Defer because "the vendor's
  detection algorithm ... is not in the strings and is a hypothesis if we
  guess it": that blocker is false.** The manual (§5.4.4.2, §5.4.7.3)
  gives the full algorithm and default parameters precisely: an event is
  a SpO2 drop of >= 4% (configurable, "Percent Drop For Event") lasting
  >= 10s ("Minimum Event Duration"); `Index(1/hr)` = event count per hour;
  `Adjusted Index(1/hr)` = event count per hour of *effective* time
  (excluding `Artifact(%)`, the excluded/zero-value fraction);
  `Avg Low SpO2(%)` = average of each event's minimum SpO2. A parallel
  pulse-rate event uses >= 6 bpm change ("Rate Change For Event") for
  >= 8s. This is no longer "a hypothesis if we guess it" -- it's
  published. Doesn't by itself flip the verdict to Adopt (item 5's other
  stated reason -- "a diagnostic-looking number from a hobby tool" --
  still stands on its own and wasn't addressed by finding the manual),
  but the specific blocker cited is gone; worth revisiting with that in
  mind rather than citing "unknown algorithm" again.
- **Item 6 ("Basal SpO2"), marked Defer because "meaning not stated
  anywhere we can see": also resolved.** The manual defines it plainly:
  "the average value of SpO2 total" -- i.e. just the mean SpO2 across the
  whole recording, already equivalent to what v0.4.13 already shows as
  "SpO2 avg". No separate feature needed; the label was the only unknown,
  and it's just a synonym for what's shipped.

**New candidate feature T-007's table has no row for at all: manual
"Exclude data"** (§5.4.2). Drag-select a region directly on the trend
chart to mark it excluded from all analysis/statistics (shown hatched;
`Undo Current` / `Undo All` to reverse) -- a user correcting for a visible
artifact (movement, a brief re-seat of the probe) they noticed, not
automatic detection, and distinct from item 9's deferred "shade
finger-out automatically". Not evaluated, not adopted here -- flagging
for whoever next touches the viewer or T-007-style evaluations to
explicitly adopt/defer/skip with a reason, same as every other candidate.

---

## Execution Notes

**`fiedle400/spo2_viewer.py`** (v0.4.18). Three changes to the page template,
nothing else in the product:
- **Channel switches:** a checkbox in front of each legend entry. An off channel
  is not drawn, loses its axis labels and is left out of the hover tooltip.
  The statistics table always covers both channels (the switch is a view
  option, not a filter).
- **Time-below level:** a number field (50 to 99, default 90) under the table.
  Values that are empty or out of range are ignored, so half-typed input
  does not break the table.
- **Print:** a Print button calling `window.print()` (the browser's own
  dialog), an `@media print` stylesheet (hides buttons, checkboxes, the level
  field and the tooltip; keeps the legend dots with `print-color-adjust`),
  and a redraw on `beforeprint`/`afterprint` so the canvas matches the page width.

**Checked in a real browser (headless Chromium), not in CI:** generated a
300-record page with a 20 s probe-out gap and an 8-point dip, toggled each
channel, typed a new level (the "time below" row changed from 90% to 94%
as expected), and printed to PDF: chart, legend dots and statistics all
appear on one page, no page errors. CI has no browser, so it cannot repeat
this.

**Tests** (`tests/test_spo2_viewer.py`, `TestViewerControls`, 4 tests): the
controls, the print button and stylesheet and the default level are present
in the generated page, and the page contains no `http://`, `https://` or
`//` source. These check markup only and need no browser, which keeps
`.github/workflows/tests.yml` unchanged. Full suite: 289 run, OK (skipped=15).

**Judgement calls.**
- The "Exclude data" feature from the manual (§5.4.2, noted above) is
  **deferred**. A user-marked exclusion changes every statistic, so it needs a
  clear "excluded" display and an undo, and nobody has asked for it. The
  manual's definition of "Basal SpO2" (mean SpO2) is already covered by the
  "SpO2 avg" row, so T-007 item 6 needs no feature. T-007 item 5 (desaturation
  events) stays deferred: its algorithm is now published, but it would still be
  a diagnostic-looking number from a hobby tool, which is a decision for psytrap,
  not part of this ticket.
- **Found while doing this:** the viewer is only reachable from the wizard,
  while `plot` takes any `.spo2`/`.csv`/`.json` file. T-006 cannot be executed
  until the viewer can open an existing file. That is filed as **T-013**
  (see T-009's notes).
- Version bumped 0.4.17 to 0.4.18 (one patch bump for this change set).
