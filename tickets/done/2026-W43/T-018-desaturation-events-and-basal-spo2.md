# T-018: Show desaturation events, ODI and Basal SpO2 in the HTML viewer

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/desat.py` (new: detector and report values)
  - `fiedle400/spo2_viewer.py` (statistics panel and chart)
  - `SPO2_FORMAT.md` §7 (the vendor definitions this implements)
  - `tickets/done/2026-W43/T-017-desaturation-and-basal-spo2-definitions.md`
    (research this follows up on)

---

## Description & Context

Placeholder opened at psytrap's request together with T-017, to hold the
implementation of the definitions T-017 researched. T-007 items 5
(desaturation events and index) and 6 ("Basal SpO2") were deferred because
no definition existed; `SPO2_FORMAT.md` §7 now has one, decoded from
`SpO2.exe` and the vendor manual.

Not ready to execute yet. Before it is, decide:
- whether to follow the vendor algorithm exactly (§7.2: baseline = local
  peak, depth >= 4 %, 10-180 s descent, merge on <= 1 % rebound) so the
  numbers match SpO2 Assistant, or a standard ODI definition, or both
  labelled clearly;
- which values to show (Total Event, Index, Adjusted Index, Avg. Low SpO2,
  Basal SpO2, Artifact %) and whether the events are marked on the chart;
- what to check it against: **T-019 is done** (2026-10-20) -- three real
  SpO2 Assistant runs (default, drop=3, min_time=8) all matched the
  §7.2 acceptance formula's predicted event counts exactly, so the decoded
  algorithm can be implemented against with confidence. The one open item
  is Basal SpO2 reading +0.8 pts higher than a flat mean in every run
  (still *inferred*, not confirmed by disassembly, per §7.1) -- implement
  against the vendor's observed behavior (whatever it's doing to read
  higher) if a confirmed definition doesn't turn up before this starts, and
  note the uncertainty rather than silently picking one.

---

## Criteria

- [x] Scope above decided with psytrap and this ticket updated.
- [x] Values match SpO2 Assistant on the T-019 probe recording (already
      validated algorithmically; re-check once implemented), or the
      difference is explained.
- [x] A test that fails without the change.
- [x] Version bumped via `scripts/bump_version.py` (product-code change).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (cloud, patch 0024, v0.4.20). Scope decided with the defaults below;
psytrap asked for "sync and execute T-018" without changing them.

- **Decisions.** Follow the vendor algorithm exactly (§7.2, validated by T-019), no
  separate standard ODI. Values shown in the viewer's statistics: Desaturation events
  (count, with the parameters), Event index and adjusted index, Average lowest SpO2 of
  events, Events below 88 % with their average low, Basal SpO2. Events are marked as red
  bands from the start of the fall to the nadir. Fixed parameters (4 %, 10-180 s, criteria
  88 %); no input fields for them yet.
- **Code.** New `fiedle400/desat.py` holds the detector and `summarize()`;
  `scripts/make_desat_probe.py` now imports it (its output files are byte-identical to
  before). `spo2_viewer.build_viewer_html` computes events in Python and injects them as a
  second JSON block (`spo2-events`); the page JS only draws them.
- **Basal SpO2.** The vendor's rule is not decoded; the plain mean reads 0.8 points lower
  than SpO2 Assistant. Implemented as the mean of valid samples outside the event falls
  (start to nadir): 96.23 on the probe vs 96.2 printed by the program. Another rule fits
  equally well (mean of samples >= 88 gives 96.21), so the viewer labels it "Basal SpO2
  (estimate)" and says the rule is not confirmed. The two rules would differ on real data.
- **Check against the real program** (T-019 values for the probe, `tests/test_desat.py`):
  7 / 8 / 9 events for default, drop 3, min duration 8; Index 9.65 (printed 9.7); Avg. Low
  SpO2 88.71 (88.7); events below 88 %: 2 with average low 79.5; average event duration
  53.3 s; Basal 96.2. All match.
- **Tests.** 316 pass (301 before): `tests/test_desat.py` (detector cases, the probe values
  above, edge cases) and three viewer tests. The page itself was opened in headless Chromium
  with the probe recording: no console errors, the statistics table and red bands as
  expected. The JavaScript is not unit-tested (no browser in CI).
- **Not done.** Pulse-rate events (detector not decoded), changing the parameters in the
  page, the `drop=3,min_time=8` combination from the real program (T-019 did not run it).
- **Gap in this validation, found afterward (T-022, 2026-10-20).** Everything checked above
  used one continuous recording -- the T-019 probe. `detect_events`/`summarize` take a flat
  `spo2` list and treat every adjacent pair of entries as one real second apart; so does the
  viewer's chart (`x(i)`, index-based). Neither has any concept of a real time gap between
  records. Fed a real multi-session download (two sessions, ~3 real minutes apart,
  concatenated with no padding -- the exact data `fiedle400 download`'s "open in the HTML
  viewer now?" path hands to the viewer), the detector reports a fabricated event spanning
  the session boundary, and the chart draws a straight line through the gap. Not a flaw in
  the per-second detection logic itself (that's still exactly validated against the real
  program for continuous data) -- it's that nothing here was ever checked against
  discontinuous data, and it turns out the implementation silently assumes continuity
  everywhere. Tracked and to be fixed in T-022, not reopening this ticket.

