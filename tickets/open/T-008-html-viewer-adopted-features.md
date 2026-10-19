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
`archive/bruteforce/SpO2.exe`) and adopted four items. T-005's viewer exists (v0.4.12) and already draws both traces
on two axes; T-006 (remove `plot`) waits on this ticket for parity.

Adopted:
1. **SpO2 and pulse trace with a switch per channel** (vendor: `BTN_Spo2GraphEnable`,
   `BTN_PRGraphEnable`).
2. **Choose the time window, with zoom and pan** (vendor: "Time Interval", strip chart report).
3. **Summary numbers**: minimum and average SpO2, average and lowest pulse, and the time
   below a chosen SpO2 level (vendor: "Minimum SpO2", "Avg. Pulse Rate", "Time(min) <").
4. **Print** with the browser's own print and a print stylesheet.

Precondition for all four: records at the sentinel values (SpO2 127, pulse 255; see
`SPO2_FORMAT.md`) are probe-out, never readings. They must not be drawn as data or
counted in any statistic. The viewer already breaks a line at a missing value; check that
sentinels never reach it as numbers. No real finger-out recording exists yet (T1), so this is tested with
synthetic records only and has to be said so in the viewer's notes.

Not adopted, with reasons: see the table in T-007 (events and index, distributions, alarm
lines, smoothing and image export are deferred; file exports, side-by-side, editing, patient
data, live view, PI and colour/language are skipped).

---

## Criteria

- [ ] Sentinel records are neither plotted nor counted in any statistic. The viewer already breaks a line at a missing value; check that
sentinels never reach it as numbers.
- [ ] Per-channel switch, time-window selection with zoom and pan, summary numbers and
      print work.
- [ ] Summary numbers are plain arithmetic on the samples; no clinical index is shown.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
