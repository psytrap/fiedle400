# T-026: Refine T-025's saturation parameters based on user feedback

- **Status:** Open (placeholder)
- **Priority:** Low
- **Owner:** Local or Cloud (depends on what the feedback turns out to need)
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`#dropPct`/`#minDur`/`#critLevel` inputs,
    `detectEvents`/`summarizeEvents`)
  - `tickets/done/2026-W43/T-025-viewer-configurable-saturation-parameters.md`
    (what shipped, for reference)

---

## Description & Context

Placeholder opened at psytrap's request to hold feedback on T-025's
configurable desaturation parameters (drop %, min duration, criteria
level) once it's actually been used -- layout, wording, defaults, ranges,
anything that doesn't feel right in practice, not a specific issue
identified yet.

**Not T-025's own engineering loose ends.** Those (criteria's unverified
range, pulse-rate parameters, no automated JS test, interaction with
T-023) are a separate concern, filed under a different framing; this
ticket is specifically for usage feedback from psytrap, not an
engineering follow-up list.

---

## Criteria

- [ ] Feedback collected and written into this ticket's Description.
- [ ] Each piece of feedback addressed, or explicitly deferred with a
      reason, not silently dropped.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
