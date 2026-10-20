# T-017: Research the vendor's desaturation-event and "Basal SpO2" definitions

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local artifact --
    same static-analysis target T-007 already mined)
  - `tickets/done/2026-W43/T-007-html-viewer-feature-evaluation.md` (items 5
    and 6, source of this ticket)
  - Any vendor manual/PDF already gathered for T-008 (see
    `9cba726 T-008: add findings from SpO2 Assistant's PDF manual, not just
    exe strings`)

---

## Description & Context

T-007's evaluation of the HTML viewer's candidate features left two items
explicitly **Defer**, both blocked on the same gap: a label or summary value
exists in SpO2 Assistant, but *how it's computed* was never found --

- **Item 5 -- Desaturation events and index.** Strings confirm the concept
  exists (`STR_Spo2EventChange` "Desaturation Event: drop in SpO2 by at
  least ... for a minimum duration of ... seconds", `STR_LeastDuration`,
  "Total Event", "Index(1/hr)", "Adjusted Index(1/hr)", "Artifact(%)",
  `STATIC_DesaturationCriteriaLevel`), but the actual algorithm -- what
  counts as the baseline before a drop, how artifact is excluded, what the
  default drop-depth/duration thresholds are -- is not visible in the
  strings alone.
- **Item 6 -- "Basal SpO2".** Only the label (`STR_BasalSpo2`) was found;
  no definition anywhere in the static analysis.

**This ticket is research and analysis only. Do not implement anything in
the viewer or anywhere else in `fiedle400` as part of this ticket.** The
explicit goal is a written, sourced definition of each term (or a documented
conclusion that no definition can be found), so a future implementation
ticket does not have to guess. T-007 was explicit that guessing either
definition is not acceptable.

Concrete avenues, not a committed list:
- Re-examine `archive/bruteforce/SpO2.exe` with deeper static analysis than
  plain `strings` -- e.g. disassembly around the `STR_Spo2EventChange`/
  `STATIC_DesaturationCriteriaLevel`/`STR_BasalSpo2` string references, the
  way `PROTOCOL.md` §3.15's Manual-mode discovery was done -- to find the
  actual threshold constants and the computation, not just the label.
- Check any vendor manual/PDF already on hand (per the T-008 commit note
  above) for a user-facing explanation of either term, even an informal one.
- Check whether OSCAR's own source (already consulted for T-004/`SPO2_FORMAT.md`
  §5.2) implements or documents an equivalent desaturation-index calculation
  for CMS50-family imports -- it's a plausible independent source for a
  standard definition even if it doesn't match the vendor's own.
- If genuinely nothing further turns up beyond what T-007 already found,
  say so plainly rather than stretching inconclusive evidence into a
  definition.

---

## Criteria

- [x] A written, sourced definition for the desaturation event/index
      (drop-depth threshold, minimum duration, baseline method, artifact
      handling) -- each part backed by a specific source (disassembly
      finding, manual text, OSCAR code reference), not inferred.
- [x] A written, sourced definition for "Basal SpO2", or an explicit
      documented conclusion that it could not be found and why.
- [x] Findings recorded in this ticket's Execution Notes; if a definition is
      found, also added to `SPO2_FORMAT.md` as reference material (not as a
      `fiedle400` feature spec -- no behavior changes here).
- [x] No code changes to `fiedle400/` or its tests as part of this ticket.
- [x] If a definition is found and is solid enough to implement against,
      this ticket's Execution Notes say so explicitly and name the follow-up
      ticket to open for the implementation (do not implement it here).

---

## Execution Notes

Done 2026-10-20 (cloud, patch 0023). Full write-up with addresses and sources:
`SPO2_FORMAT.md` §7. Summary:

- **Basal SpO2** = "the average value of SpO2 total", i.e. the mean SpO2 of the recording
  (manual §5.4.7.3). Not traced in the exe; whether artifact/excluded samples are left out of
  the mean is inferred, not verified.
- **Desaturation event**, decoded from `SpO2.exe` (`0x535430`, `0x535710`, `0x535df0`,
  `0x535f60`), defaults set at `0x531e96`/`0x53215b`:
  - baseline: the last sample before SpO2 starts falling (local peak), not a moving average;
  - event = non-increasing run from that peak to the nadir; depth = peak - nadir,
    duration = samples from peak to nadir (1 Hz, so seconds);
  - accepted if depth >= 4 % (`drop`), 10 s <= duration <= 180 s, depth/duration < 2
    (steeper falls rejected), and all samples within 0..100 (probe-out `0x7F` breaks it);
  - partial descents are merged when the rebound between them is <= 1 % and the gap is
    <= `min_time`.
- **Index** = events per hour; **Adjusted Index** uses effective time (total minus zero-value
  and excluded data); **Artifact %** = that non-effective share; **Avg. Low SpO2** = mean of
  event nadirs (all manual §5.4.7.3).
- **Criteria level** (Time <88%) default 88 % verified: global `0x6263cc` is 88 in `.data`,
  only the Analysis Para dialog writes it (`0x4fc007`).
- Not determined: whether excluded ranges are cut before detection (inferred: yes) and the
  pulse-rate event detector (defaults 6 bpm / 8 s are verified, the algorithm is not).
- No real exported SpO2 Assistant report was found online to cross-check counts against;
  forums only carry screenshots. A real report from psytrap's own recording with default
  parameters would be the check. That check is part of T-018.
- The definition is solid enough to implement against. Follow-up: **T-018** (opened in this
  patch as a placeholder), after **T-019** validates it in the real program with the probe
  from `scripts/make_desat_probe.py`. No code changes to `fiedle400/` here.
