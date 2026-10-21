# T-070: Fresh real SpO2 Assistant run of the desaturation-event probe

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `SPO2_ASSISTANT_CHECKS.md` (the procedure)
  - `scripts/make_desat_probe.py`, `output/t019-probe/probe-desat.SpO2`
  - `tickets/done/2026-W43/T-019-validate-desat-algorithm-in-spo2-assistant.md`
  - `tickets/open/T-047-release-v0-4.md` (this cycle's re-validation line
    item, closed by inspection rather than a fresh run)

---

## Description & Context

T-047's "re-run the desaturation-algorithm validation against the real
SpO2 Assistant" line item was closed by inspection (2026-10-21): since
`desat.summarize`'s values didn't change between T-019 and now, and
T-044 only fixed how the viewer *displays* those already-validated
values, the check confirmed by reading code and the probe's embedded
summary that the shown numbers match what T-019 already got from the
real program -- no new SpO2 Assistant run was done this cycle.

That's a reasoned shortcut, not a fresh confirmation. This ticket is to
actually open the probe (or a newly generated one) in the real SpO2
Assistant again, end to end, the way T-019 did the first time -- useful
as a periodic sanity check that nothing about the vendor program's own
behavior has drifted, and to have an up-to-date report on file rather
than relying on a comparison against a capture from a different day.

## Criteria

- [ ] `scripts/make_desat_probe.py` run fresh; `probe-desat.SpO2` opened
      in the real SpO2 Assistant (Windows laptop, T-053's procedure)
- [ ] Report (Bericht) exported, XML and screenshot kept per
      `SPO2_ASSISTANT_CHECKS.md` §4
- [ ] Compared against `expected.json` and against T-019's original
      table; every difference (if any) listed
- [ ] `SPO2_FORMAT.md` §7 updated if anything differs from what's
      currently documented
- [ ] Tests pass

## Execution Notes

(Not started.)
