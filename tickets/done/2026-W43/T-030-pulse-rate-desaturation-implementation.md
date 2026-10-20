# T-030: Implement the pulse-rate desaturation detector

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Blocked by:** none. The block on [T-035](T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md)
  was lifted by psytrap on 2026-10-20 (implement now, validate in the real program later).
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

- [x] `fiedle400/desat.py` implements the pulse-rate detector, with tests
      matching T-029's decoded algorithm and the T-035 probe predictions. (Not
      "validated real-program numbers": that check is deferred to T-035.)
- [x] Viewer's pulse-rate inputs are live (no longer `disabled`/dummy):
      pre-filled from Python, live recompute, following T-025's pattern.
- [x] Dummy wording/styling and `TestViewerDummyPulseInputs` removed and
      replaced with real-functionality tests.
- [x] A test per adjustable pulse parameter that fails without the change
      (same standard T-025 set for the SpO2 side).
- [x] Version bumped via `scripts/bump_version.py` (product-code change).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20, in 0.4.27 (patch 0029; the applied 0028 was an earlier draft without it).

**Caveat: the decoded algorithm is not yet checked in the real SpO2 Assistant.** Everything
here follows `SPO2_FORMAT.md` §7.3 (static decode) and the predictions of
`scripts/make_pulse_basal_probe.py`. psytrap deferred the real-program check, T-035, on 2026-10-20.

- `desat.summarize_pulse(pulse, events)`: count, index, adjusted index (events*3600/valid),
  artifact %, average event duration, same rounding as `summarize`. Valid pulse is 1..250 as
  elsewhere in fiedle400 (the detector's own range is 0..254), so artifact % may differ from the
  program at the margins; T-035 can settle it.
- `build_viewer_html` injects `analysis.pulse = {events, summary, params}`. The two inputs are live,
  pre-filled from `analysis.pulse.params`, validated like the SpO2 ones (2-20 bpm, 1-180 s), and
  recompute in the page. Dummy wording, titles and grey styling are gone, as is the
  "decoded, not shown yet" note.
- The JS reuses `detectEvents` with optional `hi`/`invalid` arguments (pulse: 254/255), plus
  `summarizePulse`; `pyRound`/`r1`/`r2`/`sum` moved up so both summaries share them, all inside the
  `desat-port` markers.
- Pulse events are amber bands on the chart, drawn only while the heart-rate checkbox is on. A new
  "Pulse-rate events" statistics group shows count, index (adjusted) and average duration.

Tests: `TestSummarizePulse` (test_desat.py); pulse parity cases (above 100, 255/None gaps, rise,
seeded fuzz, summary) in test_desat_js_parity.py; `TestViewerPulseRateEvents` replaces
`TestViewerDummyPulseInputs`. Suite green, pyflakes only the two known warnings.
