# T-076: Checkbox to toggle drawing desaturation/pulse-rate event bands in the HTML viewer

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`#legend` div ~line 61-63, `render()`'s
    event-band drawing ~line 383-402, the `show` object ~line 278)

---

## Description & Context

The HTML viewer draws desaturation events as red bands (with `show.spo2`)
and pulse-rate events as amber bands (with `show.heart_rate`), but there
is no independent control for the event bands themselves -- they are
only on or off as a side effect of the SpO2/heart-rate channel
checkboxes. Toggling the SpO2 channel off, for example, also hides the
desaturation bands even if someone just wants to compare the series
without the bands while keeping the channel itself visible.

Add a separate checkbox (or checkboxes, one per event type) to the
legend that controls only the event-band drawing, independent of the
channel switches.

**Merged 2026-10-27 with [T-068](../done/2026-W44/T-068-viewer-desaturation-event-legend.md)**
("Legend entry for desaturation/pulse event markers," no toggle, just a
swatch + label) -- not quite the same ask, but implementing this ticket's
checkbox means adding exactly the labeled legend entry T-068 wanted; there
is no reason to add an unlabeled toggle and separately add a label for the
same band later. T-068 is closed as superseded; its swatch-per-event-type
requirement is folded into this ticket's criteria below so it isn't lost.

## Criteria

- [ ] A checkbox in `#legend`, with a color swatch matching the band
      (red for desaturation, amber for pulse-rate -- from T-068), that
      toggles desaturation (red) event bands on/off, independent of the
      SpO2 channel switch
- [ ] A checkbox (with its own matching swatch) that toggles pulse-rate
      (amber) event bands on/off, independent of the heart-rate channel
      switch (or one combined checkbox for both event types, whichever
      reads better next to the existing channel switches -- psytrap's
      call when this is picked up)
- [ ] Hiding a channel still hides that channel's events too (a channel
      that isn't drawn shouldn't show orphaned event bands)
- [ ] Does not change the existing channel-toggle checkboxes' behavior
- [ ] Tests pass

## Execution Notes

(Not started.)
