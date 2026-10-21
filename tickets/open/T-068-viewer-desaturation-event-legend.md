# T-068: Legend entry for desaturation/pulse event markers in the HTML viewer

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`#legend` div, ~line 61; the event-marker
    drawing code the legend would need to explain)

---

## Description & Context

Raised while comparing `output/g-timing-check/manual5min.html`'s
desaturation events against the real SpO2 Assistant side by side (T-047's
G9 check, 2026-10-21): the viewer's `#legend` only has toggles for the
SpO2/heart-rate channels (`spo2_viewer.py:61-66`). It has no entry
explaining what the desaturation-event and pulse-rate-event markers drawn
on the chart look like, so a reader has to infer it from context rather
than a key.

## Criteria

- [ ] Legend adds an entry (swatch + label) for desaturation-event markers
- [ ] Legend adds an entry (swatch + label) for pulse-rate-event markers
- [ ] Doesn't change the existing channel-toggle checkboxes' behavior
- [ ] Tests pass

## Execution Notes

(Not started.)
