# T-016: Add save-as-PNG and a smooth trend overlay to the HTML viewer

- **Status:** Won't Do
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the HTML viewer template and its data build)
  - `tickets/done/2026-W43/T-007-html-viewer-feature-evaluation.md` (source of
    the candidate list and verdicts below)

---

## Description & Context

T-007 evaluated SpO2 Assistant's own feature set (via static strings) as the
reference point for the HTML viewer (T-005). The adopted items shipped as
**T-008**. Item 19 (reopen a past recording) is its own ticket, **T-013**.
This ticket is the remaining **Defer** items that are actually implementable
now, as one unit of work:

| # | Candidate | Implementation |
|---|---|---|
| 11 | Save chart as an image | "Save as PNG" button using `canvas.toDataURL()` |
| 10 | Smooth trend overlay | Toggle-able moving-average overlay, **off by default**, visibly labelled "smoothed" when on (T-007: smoothing can hide short drops) |

Explicitly **out of scope here** (stay deferred, not part of this ticket):
- Item 5 (desaturation events/index) and item 6 ("Basal SpO2") -- both need
  a definition that doesn't exist yet (vendor algorithm/label meaning
  unknown); guessing one is not acceptable.
- Item 9 (visually marking finger-out stretches) -- blocked on T1, no real
  finger-out recording exists to verify against.
- Item 7 (distribution table) and item 8 (alarm limit lines) -- dropped
  from this ticket's scope entirely (not a priority right now).

If any of the above become relevant later, they get their own ticket
rather than being folded into this one.

---

## Criteria

- [ ] Items 10 and 11 both implemented in `fiedle400/spo2_viewer.py`,
      consistent with T-008's existing per-channel-switch/zoom/print UI
      rather than a new pattern.
- [ ] Item 10's moving-average overlay defaults off and is visibly labelled
      when enabled.
- [ ] A test per item (or one test covering the generated HTML/data for
      both) that fails without the change.
- [ ] `fiedle400/__init__.py` / `pyproject.toml` version bumped via
      `scripts/bump_version.py` (product-code change, RELEASE_PLAN §1).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Closed 2026-10-20 (psytrap: "close t16 as wont do"), no reason beyond that
given. Neither item 10 (smooth trend overlay) nor item 11 (save-as-PNG) was
implemented; nothing in `fiedle400/spo2_viewer.py` changed. If either item
becomes wanted later, re-open a fresh ticket rather than reopening this one
-- the surrounding scope (T-007's full candidate list, what's since shipped
via T-008/T-018) may have moved on by then.
