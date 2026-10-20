# T-026: HTML viewer design and format feedback

- **Status:** Open
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the whole generated page: layout, wording,
    legend, stats table, parameter groups)

---

## Description & Context

Originally opened as a narrower placeholder for feedback on T-025's
saturation parameters specifically. Retitled 2026-10-20: psytrap's
feedback turned out to be about the viewer's HTML design and format in
general -- layout, grouping, wording, spacing -- not limited to the
saturation-parameter inputs. This ticket now tracks that broader, ongoing
review.

**Not T-025's own engineering loose ends.** Those (criteria's unverified
range, pulse-rate parameters, no automated JS test, interaction with
T-023) stayed a separate concern, now split into
[T-027](T-027-js-detection-logic-test-coverage.md)/
[T-029](T-029-pulse-rate-desaturation-decode.md)/
[T-030](T-030-pulse-rate-desaturation-implementation.md)/
[T-031](T-031-basal-spo2-rule-confirmation.md)/
[T-032](T-032-desaturation-algorithm-review.md). This ticket is
specifically for design/format feedback from psytrap, not an engineering
follow-up list.

This is a live, ongoing review -- each round of feedback has been applied
directly (per `tickets/README.md`: "if you're told to do something, do
it"), with this ticket opened after the fact to give the series a
permanent record rather than gating any of the individual changes.

---

## Criteria

- [ ] Feedback collected and addressed, logged in Execution Notes as it
      comes in.
- [ ] Each piece of feedback addressed, or explicitly deferred with a
      reason, not silently dropped.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

In progress, 2026-10-20 (local, direct instruction per round -- same basis
as T-004/T-025). Applied so far, each its own commit:

- Dummy, disabled pulse-rate parameter row added (greyed out, explicitly
  labelled not functional, T-029/T-030) so the real dialog's layout could
  be previewed ahead of a real detector existing.
- Parameter rows restructured from run-on sentences into a 2-column
  table/grid (label left, input+unit right) -- chosen from four
  prototyped layouts shown to psytrap.
- The three parameter groups (time-below, desaturation event, pulse-rate)
  visually separated with dividers/spacing, each given a bold, colon-free
  heading line.
- "criteria level" reworded to "count event as severe if under" (and
  corrected to strictly "under", not "at or under", matching desat.py's
  actual `<` comparison).
- Parameter groups now print (`@media print` no longer hides them).
- Stats table reordered and grouped into "Recording" vs. "Desaturation
  analysis" blocks; "Event index" and "Events below X%" moved next to
  "Desaturation events".
- Timestamps in the header line display with a space instead of ISO's
  "T" separator; header line reordered to timestamps-then-duration
  instead of leading with the record count (still shown in the Duration
  stats row).
- **Real bug found and fixed, not just cosmetic:** "Time below level" had
  its own independently-adjustable input (defaulting to 90%), unrelated
  to the criteria level used for event severity. The real SpO2 Assistant
  ties them together (`SPO2_FORMAT.md` Sec7.1: "Time (min) <88%" uses the
  same desaturation criteria level). Fixed to match -- removed the
  separate input, "Time below X%" now reads the criteria value directly.
  Spun into [T-032](T-032-desaturation-algorithm-review.md) as a prompt
  to systematically check for other cases of the same failure mode.
- Wording trims: "SpO2 Assistant method" / "Assistant method" dropped
  from the desaturation-events stats row (redundant with the group
  heading); "fixed" dropped from the channel legend, "range" added
  instead.
- The fixed `max_time` constant (180s, not adjustable, matching the real
  dialog) shown as a readonly input box instead of plain text, so it
  reads consistently with the other parameter inputs.
- Dummy pulse-rate note ("not functional -- T-029/T-030") moved out of
  the bold heading to its own note line, matching where the SpO2 group's
  own "(pulse-rate events: not decoded...)" note sits.
- Basal SpO2's "not confirmed" wording now cites
  [T-031](T-031-basal-spo2-rule-confirmation.md) instead of asserting the
  gap with no pointer to where it gets resolved.

337 tests pass throughout (5 net new from the dummy pulse-input tests).
Still open -- review is ongoing, more feedback expected.
