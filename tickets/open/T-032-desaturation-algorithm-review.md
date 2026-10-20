# T-032: Review the desaturation-event algorithm against the decoded spec

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local or Cloud
- **Scope & Relevant Files:**
  - `fiedle400/desat.py` (`detect_events`, `summarize` -- the Python
    implementation)
  - `fiedle400/spo2_viewer.py` (`detectEvents`/`summarizeEvents`, its JS
    port; the viewer's parameter inputs and stats rows that consume both)
  - `SPO2_FORMAT.md` §7.1/§7.2 (the decoded spec both implementations are
    supposed to match)
  - `tests/test_desat.py` (existing coverage, to check what it does and
    does not exercise)

---

## Description & Context

A recent pass over the viewer (2026-10-20) found that "Time below level"
had its own independently-adjustable input (`#desatLevel`, defaulting to
90%) unrelated to the desaturation criteria level, when the real SpO2
Assistant actually drives "Time <X%" from the *same* criteria value that
classifies event severity (`SPO2_FORMAT.md` §7.1: "Time (min) <88% ...
desaturation criteria level"). That divergence had shipped since T-008
(v0.4.18) and gone unnoticed through T-018/T-019/T-025 -- not because it
was hard to find, but because nobody had specifically checked the viewer's
behaviour line-by-line against `SPO2_FORMAT.md`'s own decoded definitions.

**What this ticket is:** a systematic read-through of `desat.py` and its
JS port against `SPO2_FORMAT.md` §7.1 (report values) and §7.2 (event
algorithm), field by field and parameter by parameter, specifically
looking for other cases of the same failure mode -- a value, threshold,
or relationship that was implemented independently of what the decoded
spec (or the real SpO2 Assistant, where T-019's screenshot/report data is
available) actually says. Not a request to re-derive the algorithm from
scratch -- T-017/T-019 already did that validation work for the core
event-acceptance logic itself (drop/min_time/max_time/max_avg/
oscillation all matched in T-019's three real runs). This is specifically
about everything *around* that core logic: which report values share a
parameter vs. have their own, which stats are derived from which inputs,
and whether the viewer's UI groups/wiring reflect that correctly.

Known open items this review should take into account (not duplicate):
- T-029/T-030: pulse-rate side is unimplemented, out of scope here.
- T-031: Basal SpO2's exact averaging rule is already a known unconfirmed
  item with its own ticket.
- T-027: JS/Python parity testing is a separate, already-ticketed concern
  (this ticket's findings may feed test cases into it, but T-032 itself
  is a review pass, not the automation effort).

---

## Criteria

- [ ] Every report value in `SPO2_FORMAT.md` §7.1 checked against what
      `desat.py`/the viewer actually compute and display, with each one
      marked consistent or logged as a discrepancy in this ticket's
      Execution Notes.
- [ ] Every adjustable/fixed parameter in §7.2 checked against the
      viewer's inputs for the same kind of sharing-vs-independent mistake
      the Time-below-level bug was.
- [ ] Any discrepancies found are either fixed (with tests) or spun off
      into their own tracked ticket if they need their own decode/
      validate cycle -- not silently left as review notes with no
      follow-up.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
