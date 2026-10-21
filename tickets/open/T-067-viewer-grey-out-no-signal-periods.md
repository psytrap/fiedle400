# T-067: HTML viewer should grey out no-signal/probe-out periods on the chart

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (chart rendering, band drawing)

---

## Description & Context

Noticed 2026-10-21 while reviewing a 5-minute manual-mode recording
(`output/g-timing-check/manual5min.html`) with a deliberate ~20s finger-out
in the middle. The viewer already draws colored bands for other
per-sample conditions -- red for desaturation events, amber for
pulse-rate-fall events (`spo2_viewer.py` lines ~392, ~496) -- but a
no-signal/probe-out stretch currently has no equivalent visual marker on
the chart itself. The summary table below the chart does report
"No-signal / probe-out" as a count + percentage, but you have to look at
the chart, notice a gap or flat/odd segment, and then cross-reference the
table to realize what it is.

psytrap wants no-signal/probe-out periods marked with a grey band on the
chart (same mechanism as the existing red/amber bands), so they're
visually obvious without needing the summary table.

---

## Criteria

- [ ] No-signal/probe-out stretches are drawn as a grey band on the chart,
      consistent with the existing red (desaturation) / amber (pulse-rate)
      band styling
- [ ] Works for both a single contiguous no-signal stretch and multiple
      separate ones in the same recording
- [ ] Existing red/amber bands and the "No-signal / probe-out" summary row
      are unaffected
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
