# T-086: Clean up `fiedle400/desat.py`

- **Status:** Done
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/desat.py`

---

## Description & Context

`desat.py` implements the SpO2/pulse desaturation-event detector and the
report-value summaries derived from it, reverse-engineered from SpO2
Assistant and cross-checked against real decoded behavior (see the
module docstring for the T-ticket trail: T-019, T-022, T-029-T-031,
T-035, T-044). It works and is validated against the real program for
the covered cases, but it was written dense and terse to stay close to
the decompiled reference logic while reverse-engineering it, not for
long-term readability:

- `_detect`'s state machine (`st`, `en`, `x`, `c`/`cand`, `cur`, `n`)
  uses single/short-letter names throughout with no inline explanation
  of what the running state represents at each branch.
- `summarize` and `summarize_pulse` repeat the same shape of formula
  (`index_per_hr`, `adjusted_index_per_hr`, `artifact_pct`,
  `avg_event_duration_s`) with slightly different valid-sample
  predicates (`1 <= v <= 100` vs `1 <= v <= 250`) and no shared helper.
- Several comments point at specific decompiled addresses
  (`0x54ced1-0x54d059`, `0x532b39`) and ticket numbers as the only
  explanation for *why* a formula is shaped the way it is -- fine as
  provenance, but the surrounding code has little of its own narrative.

This is purely a readability/maintainability pass -- not a correctness
fix. T-035 (pulse detector not yet validated against the real program)
is separate, already its own ticket, and out of scope here.

## Criteria

- [x] `_detect`'s state variables renamed/commented so the state
      machine's logic (candidate descents -> accepted events) reads
      clearly without cross-referencing SpO2 Assistant's decompiled
      addresses
- [x] Shared formula logic between `summarize` and `summarize_pulse`
      factored out (or at least clearly parallel), without changing
      any computed values
- [x] General good-practice pass while in here: clear naming,
      functions doing one thing, no dead code/commented-out blocks,
      docstrings kept accurate to the renamed/refactored code (not
      just preserved as-is if they now describe stale internals)
- [x] `tests/test_desat.py` (already has 29 cases) extended to cover
      any internal helper(s) this refactor introduces (e.g. a factored
      formula helper, or renamed state-machine pieces worth testing in
      isolation), not just the existing black-box
      `detect_events`/`summarize` coverage -- and held to the same
      good-practice bar as the production code: clear/descriptive test
      names, no copy-pasted near-duplicate cases, one behavior asserted
      per test rather than several unrelated assertions bundled
      together
- [x] No behavior change: existing tests covering `desat.py` still pass
      unchanged, and detected events/report values are bit-for-bit
      identical on the T-019/T-029-T-031 probe recordings used to
      validate this module originally
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

**2026-10-23 (Claude):** `_detect` split into three single-purpose
helpers (`_find_descent_candidates`, `_is_accepted_event`,
`_merge_and_accept`), with `st`/`en`/`x`/`c`/`cur`/`n` renamed to
`descent_start`/`descent_end`/`values`/`candidate`/`current`/etc. and a
comment calling out the `0`-as-"no descent open" sentinel quirk
explicitly (preserved as-is, not "fixed", since that would change
behavior). `summarize`/`summarize_pulse` now share
`_valid_indices`, `_event_rate_stats`, and `_avg_event_duration` instead
of repeating the same formula shape.

No computed value changed: full suite (421 tests, up from 413) passes,
including the exact-value checks against the T-019 real-SpO2-Assistant
probe recording and the JS-parity tests. Added 8 new focused unit tests
for the three new helpers (`TestValidIndices`, `TestAvgEventDuration`,
`TestEventRateStats`) in `tests/test_desat.py`, one behavior per test.
