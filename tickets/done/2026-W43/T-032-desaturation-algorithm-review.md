# T-032: Review the desaturation-event algorithm against the decoded spec

- **Status:** Done
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

- [x] Every report value in `SPO2_FORMAT.md` §7.1 checked against what
      `desat.py`/the viewer actually compute and display, with each one
      marked consistent or logged as a discrepancy in this ticket's
      Execution Notes.
- [x] Every adjustable/fixed parameter in §7.2 checked against the
      viewer's inputs for the same kind of sharing-vs-independent mistake
      the Time-below-level bug was.
- [x] Any discrepancies found are either fixed (with tests) or spun off
      into their own tracked ticket if they need their own decode/
      validate cycle -- not silently left as review notes with no
      follow-up.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**§7.2 parameters (viewer wiring): clean.** Every adjustable and fixed
parameter maps to exactly one input, or isn't exposed at all, matching the
vendor's own Analysis Parameters dialog:

| §7.2 parameter | Viewer input | Range | Verdict |
| :--- | :--- | :---: | :--- |
| `drop` | `dropPct` | 1-20 | ok |
| `min_time` | `minDur` | 1-180 | ok |
| `criteria` | `critLevel` | 1-99 | ok -- one input, feeds both events-below and time-below |
| `max_time`, `max_avg`, `oscillation`, valid range | not exposed (constants) | -- | ok |
| pulse `drop` | `pulseDropBpm` | 2-20 | ok |
| pulse time | `pulseMinDur` | 1-180 | ok |

No second instance of the Time-below-level bug (the T-026 fix holds, with
tests at `tests/test_spo2_viewer.py:80,89`).

**§7.1 report values: two discrepancies, same failure shape as the bug
that opened this ticket** -- a decoded value exists and the UI displays a
separately-computed near-synonym instead:

1. `artifact_pct` is computed by both `desat.summarize` and the viewer's
   `summarizeEvents`, and never displayed. The row shown instead,
   "No-signal / probe-out", is a separate inline calculation over a
   narrower definition (excludes only `null`/`undefined`, not the full
   1..100 valid range).
2. "Time (min) <criteria" (§7.1) is not computed in either `summarize`
   path at all -- only inline in `stats()`, outside the
   `BEGIN/END desat-port` block the JS parity harness (T-027) extracts,
   and over yet another valid-sample definition. `make_desat_probe.py`'s
   `time_below_88_s` computes the same thing a third way.

Spun off as [T-044](../../open/T-044-viewer-artifact-and-time-below-discrepancies.md)
(Owner: Cloud, since fixing touches product code). Smaller items logged
there too but not promoted to criteria: the pulse-events display row reads
the SpO2 channel's `max_time` rather than its own (both are 180 today, so
harmless); the `st = 0` sentinel-index quirk from `desat.py` (a candidate opening at
sample index 0 is indistinguishable from "none open") is ported identically
into the JS, so the parity tests compare two implementations that share the
bug and will never flag it.

**Everything else matched**: Total Event, Index, Adjusted Index, Avg. Low
SpO2, Basal SpO2 (0-as-valid caveat already recorded in §7.1), and the two
German-label fields (`Ereignis<criteria`, `Durchschn. niedrige
SpO2<criteria`) are consistent between `desat.py` and the viewer's JS port.

No change to `desat.py` or `spo2_viewer.py` in this ticket -- it was a
review pass, not a fix. `SPO2_FORMAT.md` §7.2 was rewritten during this
review to lead with a single-pass description of the detector (state
carried as one active + one pending descent + a dropout flag) with the
three-function/disassembly form kept as an implementation-detail note; no
behaviour or decoded fact changed, only the exposition.
