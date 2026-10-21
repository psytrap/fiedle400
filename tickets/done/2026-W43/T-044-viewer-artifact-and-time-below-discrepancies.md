# T-044: Viewer shows a different "artifact"/"time below" than it computes

- **Status:** Done
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

- [x] `artifact_pct` (or an equivalent "No-signal / probe-out" row using the
      same 1..100 valid definition as the rest of the report) is the one
      value displayed -- not two separately-computed figures.
- [x] "Time (min) <criteria" is computed inside the shared `summarize`/
      `summarizeEvents` path (and so inside the JS parity-extracted block),
      using the same valid-sample definition as the other report values.
- [x] `scripts/make_desat_probe.py`'s `time_below_88_s` either reuses that
      same definition or the discrepancy is noted as intentional, with a
      reason.
- [x] A test fails without the fix (construct a recording with a raw `0`
      or non-null sentinel sample and show the old mismatch).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**Fixed in both `desat.py` and the JS port.** `summarize`/`summarizeEvents`
now compute `time_below_criteria_s`, counting the same `valid` (1..100)
index set already used for `artifact_pct`/`adjusted_index_per_hr`/
`basal_spo2` -- added right next to `events_below_criteria` so the shared
definition is obvious at a glance, and inside the existing
`BEGIN/END desat-port` block, so T-027's parity harness (full-dict
`assertEqual`) now covers it automatically with no changes needed there.

`stats()` no longer computes `invalidCount`/`desatCount` by filtering
`spo2Vals` on its own. Both rows now read `analysis.summary` directly:
"No-signal / probe-out" from `a.artifact_pct` / `n - a.valid_samples`,
"Time below <criteria>%" from `a.time_below_criteria_s` /
`a.valid_samples`.

`scripts/make_desat_probe.py`'s `time_below_88_s` needed no change -- it
already used the correct `valid = [v for v in s if 1 <= v <= 100]`
definition; it was `desat.py`/the viewer that were out of step with it, not
the other way round.

Tests: `tests/test_desat.py` gets a case with a raw `0` and `None` mixed,
asserting `artifact_pct` and `time_below_criteria_s` agree on the same
excluded samples; `tests/test_spo2_viewer.py` pins that the generated page
reads `a.artifact_pct`/`a.time_below_criteria_s` and no longer contains
`spo2Vals.filter`. The existing JS parity suite
(`tests/test_desat_js_parity.py`) passed unchanged, now exercising the new
field. `SPO2_FORMAT.md` §7.1's "Time (min) <88%" row updated to name the
new field and the shared definition.

Two smaller findings from the same review pass were not fixed here --
spun off as [T-045](T-045-pulse-max-time-and-sentinel-index-quirks.md)
since neither is a report-value discrepancy: the pulse stats row reading
the SpO2 channel's `max_time`, and the `st = 0` sentinel-index quirk shared
identically by `desat.py` and its JS port.

399 -> 401 tests, all green.
