# T-025: Configurable desaturation/pulse analysis parameters in the viewer

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Cloud
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

- [ ] Scope above decided with psytrap (pulse events in or out of v1) and
      this ticket updated before implementation starts.
- [ ] SpO2 parameters (drop %, min duration, criteria level) adjustable in
      the viewer page, replacing the fixed `desat.py` constants for that
      session's analysis.
- [ ] Changing a parameter visibly recomputes the events/statistics in the
      page, not just accepted and ignored.
- [ ] Pulse-rate parameters either implemented with a real (not guessed)
      detector, or explicitly left out with the reason stated in this
      ticket's Execution Notes.
- [ ] A test per adjustable parameter that fails without the change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
