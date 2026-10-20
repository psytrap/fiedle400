# T-025: Configurable desaturation/pulse analysis parameters in the viewer

- **Status:** Done
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (statistics panel line showing "Desaturation
    events ... fall of at least 4% over 10-180 s, SpO2 Assistant method")
  - `fiedle400/desat.py` (`DROP`/`MIN_TIME`/`MAX_TIME`/`MAX_AVG`/
    `OSCILLATION`/`CRITERIA` -- currently fixed constants; pulse-rate
    events not decoded at all)
  - SpO2 Assistant's own "Analyseparameter" dialog (screenshot captured
    for T-019: `output/t019-probe/windows-result/analysis-params.png`,
    not tracked in git) -- the reference UI this mirrors
  - `tickets/done/2026-W43/T-018-desaturation-events-and-basal-spo2.md`
    ("Not done: changing the parameters in the page")

---

## Description & Context

psytrap: a saturation-options panel in the viewer like SpO2 Assistant's
own "Analyseparameter" dialog (captured live during T-019), rather than
the current fixed line in the statistics table:

> Desaturation events  0 (red bands; fall of at least 4% over 10-180 s,
> SpO2 Assistant method)

**Split 2026-10-20** out of T-024, which had bundled "adjustable
parameters" together with the export/save button. They're separable:
this ticket is the parameter UI itself; T-024 is now just the export/save
mechanism, which can persist whatever this ticket produces once both
exist.

**The real dialog, for reference** (SpO2 Assistant, captured T-019):

| Section | Field | Default | Range (from the live UI) |
| :--- | :--- | :---: | :---: |
| SpO2 Parameter | Abfall fuer Ereignis (%) / drop | 4 | 1-20 |
| SpO2 Parameter | Minimum Ereignisdauer (Sek) / min_time | 10 | 1-180 |
| SpO2 Parameter | Entsaettigungsschwelle (%) / criteria | 88 | not seen live |
| Pulsrate Parameter | Pulsaenderung fuer Ereignis (bpm) / drop | 6 | 2-20 |
| Pulsrate Parameter | Minimum Ereignisdauer (Sek) / time | 8 | not seen live |

`max_time` (180, fixed), `max_avg` (2, fixed) and `oscillation` (1, fixed)
were decoded from `SpO2.exe` (T-017, `SPO2_FORMAT.md` §7.2) but the live
dialog doesn't expose them as adjustable -- matching that, this ticket's
SpO2 side should offer `drop`/`min_time`/`criteria`, not the fixed ones,
unless there's a reason to go further than the vendor's own UI.

**Pulse-rate events are not decoded at all** (`desat.py`'s docstring and
T-018's own "Not done" list both say so) -- a pulse-side parameter panel
with no detector behind it would be misleading. Either this ticket also
decodes and implements pulse events (a larger scope than parameter UI
alone), or the pulse fields are left out of v1 and explicitly noted as
why, not silently added as dead inputs.

**Not decided here, for whoever picks this up:**
- Live recompute as parameters change (client-side, needs the detection
  logic in JS too, not just Python) vs. a re-render/reload step.
- Whether `criteria`'s and the pulse fields' valid ranges need live
  verification (T-019-style) before shipping, since they weren't seen in
  the captured dialog, only decoded statically.
- Relationship to T-023 (area exclusion) if that lands first -- excluded
  ranges and parameter changes both affect the same event detection and
  should recompute together, not as two independent passes that can
  disagree.

---

## Criteria

- [x] Scope above decided with psytrap (pulse events in or out of v1) and
      this ticket updated before implementation starts.
- [x] SpO2 parameters (drop %, min duration, criteria level) adjustable in
      the viewer page, replacing the fixed `desat.py` constants for that
      session's analysis.
- [x] Changing a parameter visibly recomputes the events/statistics in the
      page, not just accepted and ignored.
- [x] Pulse-rate parameters either implemented with a real (not guessed)
      detector, or explicitly left out with the reason stated in this
      ticket's Execution Notes.
- [x] A test per adjustable parameter that fails without the change.
- [x] Version bumped via `scripts/bump_version.py` (product-code change).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (local, direct instruction "implement t25" -- same basis as
T-004 earlier this session: a direct instruction does the work regardless
of the ticket's `Owner` field, per `tickets/README.md`'s own "a ticket is
for tracking work, not gating it").

**Scope decided: pulse-rate events left out of v1.** No detector for them
is decoded anywhere in this project (`desat.py`'s own docstring and T-018's
"Not done" list both say so); a parameter panel with no real detection
behind it would be actively misleading. The page says so explicitly next
to the SpO2 parameters: "(pulse-rate events: not decoded, SpO2 only --
T-025)" rather than silently omitting them with no explanation.

**Implementation.** Three new inputs (`#dropPct`, `#minDur`, `#critLevel`)
next to the existing `#desatLevel` "time-below-level" input, pre-filled
from `analysis.params` (the same values `desat.py` used to build the
page's *initial* analysis) rather than a separately hardcoded default --
one source of truth, no drift possible between the Python-computed first
render and the input defaults. Ranges (drop 1-20, min_time 1-180, criteria
1-99) match the live SpO2 Assistant dialog captured for T-019 where that
dialog showed a range at all; `criteria`'s range wasn't visible live, so
1-99 is a reasonable bound, not a decoded fact -- noted here, not asserted
as verified in the ticket or the code.

`fiedle400/spo2_viewer.py` gained `detectEvents`/`summarizeEvents`, a
line-by-line JS port of `desat.py`'s `detect_events`/`summarize` (same
candidate-building, oscillation-merge, and acceptance logic; `max_time`,
`max_avg`, `oscillation` stay fixed JS constants, matching that the real
dialog doesn't expose them either). Any input change calls
`recomputeEvents()`, which re-derives `analysis` client-side and re-runs
`stats()`/`render()` -- no server round-trip, consistent with T-005's
static-page design.

**Verified against real data, not just unit tests.** Built the viewer page
from the T-019 probe recording (2611 records, the same one validated
against the real SpO2 Assistant three times) and drove it in a real browser
(this session's Browser-pane tool, `http://localhost`, console-clean):
  - Default load: 7 events, index 9.7/hr, basal 96.2% -- matches T-019 run 1
    exactly, confirming the JS port's initial state agrees with the
    Python-computed one it's built from.
  - Set drop=3 live: recomputed to 8 events, index 11.0/hr -- matches
    T-019 run 2 exactly.
  - Reset drop=4, set min_time=8 live: recomputed to 9 events, index
    12.4/hr -- matches T-019 run 3 exactly.
  - Set criteria=95 live: 7/7 events counted as "below", each event's
    nadir checked by hand against the threshold -- correct.
  - Screenshot confirmed the chart's red event bands visibly move/appear
    with each change, not just the stats table.

**Tests.** `tests/test_spo2_viewer.py::TestViewerConfigurableEventParameters`
(5 new tests): inputs exist with the right ranges, defaults come from
`analysis.params` in JS rather than a separate hardcoded `value=`
attribute (so the two can't drift apart), the pulse-events note is present
and no pulse input exists, and the change listener is wired to
`recomputeEvents`. The JS recompute logic itself has no unit test (no
browser in CI, same limitation T-018 already documented) -- covered by the
real-browser verification above instead. 331 tests pass (326 before).
pyflakes not installed in this environment (same gap noted in T-004's
closure); no new imports were added, so risk is low.

**Not done.** T-023 (area-exclusion selection) and T-024 (export/save)
remain separate, deferred tickets; this ticket didn't block on either.
Live verification of `criteria`'s and any future pulse parameters' exact
valid ranges against the real SpO2 Assistant (beyond what the T-019
screenshot already showed) is not done -- the 1-99 bound is a reasonable
default, not a confirmed vendor fact.
