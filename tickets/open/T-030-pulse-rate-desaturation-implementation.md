# T-030: Implement the pulse-rate desaturation detector

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Blocked by:** [T-035](T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md)
  (the real-program check of T-029's decode). T-029 is done: the decode is
  `SPO2_FORMAT.md` §7.3 and `desat.detect_pulse_events` already exists (2026-10-20);
  what is left here is the pulse summary values and the viewer.
- **Scope & Relevant Files:**
  - `fiedle400/desat.py` (SpO2-side detector to mirror; `DROP`/`MIN_TIME`/
    etc. constants and `detect_events`/`summarize`)
  - `fiedle400/spo2_viewer.py` (`#pulseDropBpm`/`#pulseMinDur` -- currently
    disabled, dummy inputs added this session purely to preview the
    layout; `detectEvents`/`summarizeEvents`, the JS port pattern from
    T-025, to be mirrored for the pulse side)
  - `tests/test_spo2_viewer.py::TestViewerDummyPulseInputs` (asserts the
    inputs are disabled and labelled dummy -- must be rewritten, not just
    deleted, once they become real)

---

## Description & Context

**Split 2026-10-20 out of T-028** alongside [T-029](T-029-pulse-rate-desaturation-decode.md);
this is the implementation half, blocked on T-029's decoded-and-validated
algorithm.

The viewer currently has a disabled, greyed-out pulse-rate parameter row
("Pulse-rate event (dummy, not functional -- T-029/T-030): change of at
least 6 bpm over 8 s") added this session so the layout matches SpO2
Assistant's real Analyseparameter dialog ahead of time, with reference
defaults (6 bpm, 8 s) confirmed live against the same probe recording used
for T-019/T-025. Nothing behind it works yet -- no detector exists.

**What this ticket is**, once T-029 lands:

1. `fiedle400/desat.py` gains a pulse-rate counterpart to
   `detect_events`/`summarize` (same candidate-building/merge/acceptance
   shape, pulse-specific constants from T-029's decode), with tests
   matching T-029's validated real-program numbers.
2. `fiedle400/spo2_viewer.py`'s `#pulseDropBpm`/`#pulseMinDur` go from
   `disabled` dummy inputs to live ones, following T-025's established
   pattern exactly: pre-filled from Python-computed `analysis.params`
   (not hardcoded separately), live client-side recompute via a JS port
   of the new Python functions, no server round-trip.
3. The "dummy, not functional -- T-029/T-030" wording and the greyed-out
   styling come out; the row reads like the SpO2 one does today.
4. `tests/test_spo2_viewer.py::TestViewerDummyPulseInputs` is replaced
   with real-functionality tests mirroring
   `TestViewerConfigurableEventParameters`.

---

## Criteria

- [ ] `fiedle400/desat.py` implements the pulse-rate detector, with tests
      matching T-029's validated real-program numbers.
- [ ] Viewer's pulse-rate inputs are live (no longer `disabled`/dummy):
      pre-filled from Python, live recompute, following T-025's pattern.
- [ ] Dummy wording/styling and `TestViewerDummyPulseInputs` removed and
      replaced with real-functionality tests.
- [ ] A test per adjustable pulse parameter that fails without the change
      (same standard T-025 set for the SpO2 side).
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
