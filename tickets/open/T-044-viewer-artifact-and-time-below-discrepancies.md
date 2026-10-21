# T-044: Viewer shows a different "artifact"/"time below" than it computes

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`summarizeEvents`, `stats()`, lines ~188-209
    and ~478)
  - `fiedle400/desat.py` (`summarize`, `artifact_pct`)
  - `scripts/make_desat_probe.py` (`time_below_88_s`)
  - `tests/test_desat_js_parity.py` (the `BEGIN/END desat-port` extraction)
  - `SPO2_FORMAT.md` §7.1

---

## Description & Context

Found during T-032's review pass over the viewer, the same failure shape as
the Time-below-level bug that opened T-032: a decoded report value exists,
and the UI displays a separately-computed near-synonym instead of it, so the
two can silently disagree.

**1. `artifact_pct` is computed and never displayed.** Both
`desat.summarize` and the viewer's `summarizeEvents` compute `artifact_pct`
(share of samples outside 1..100). Nothing in `stats()` reads it. The row
actually shown, "No-signal / probe-out", is a separate inline calculation
that only excludes `null`/`undefined`, not the full 1..100 valid range. Any
sample that is a numeric `0` or lands as a non-null sentinel (`127`) counts
as artifact in `artifact_pct` but as a valid reading in the displayed
figure.

**2. "Time (min) <criteria" is outside the shared summarize path.**
`SPO2_FORMAT.md` §7.1 lists it as a report value, but neither
`desat.summarize` nor `summarizeEvents` computes it -- it exists only
inline in `stats()` (`spo2_viewer.py` ~line 478), filtering the null-only
set rather than 1..100. Consequences: it sits outside the
`BEGIN/END desat-port` block `test_desat_js_parity.py` extracts, so T-027's
parity harness cannot cover it; a raw `0` sample counts as below-criteria
there but not in `desat.py`; and `scripts/make_desat_probe.py`'s
`time_below_88_s` computes the same thing a third way, over the 1..100
valid set, so the probe's prediction and the viewer's display use different
valid-sample definitions.

What is NOT known:
- Whether these ever produce a visibly different number on a real
  recording, or only on constructed edge cases (raw `0`, non-null
  sentinels) that may not occur in practice.

---

## Criteria

- [ ] `artifact_pct` (or an equivalent "No-signal / probe-out" row using the
      same 1..100 valid definition as the rest of the report) is the one
      value displayed -- not two separately-computed figures.
- [ ] "Time (min) <criteria" is computed inside the shared `summarize`/
      `summarizeEvents` path (and so inside the JS parity-extracted block),
      using the same valid-sample definition as the other report values.
- [ ] `scripts/make_desat_probe.py`'s `time_below_88_s` either reuses that
      same definition or the discrepancy is noted as intentional, with a
      reason.
- [ ] A test fails without the fix (construct a recording with a raw `0`
      or non-null sentinel sample and show the old mismatch).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
