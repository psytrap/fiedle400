# T-052: Re-check findings T1-T8 against this release's hardware testing

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `RELEASE_PLAN.md` §3d (findings, current status)
  - `CHANGELOG.md` (full discovery/fix history)
  - `fiedle400/cli.py` (`_probe_out_alert`, T1's mitigation)

---

## Description & Context

Tracked alongside [T-047](T-047-release-v0-4.md) and
[T-051](T-051-manual-mode-remaining-protocol-questions.md), not folded
into either: `T1`..`T8` are hardware/protocol **findings**, a separate,
older numbering scheme from before the ticket system existed (`AGENTS.md`
glossary) -- tracked in `RELEASE_PLAN.md` §3d / `CHANGELOG.md`, not
`tickets/`. This release's own hardware testing (T-047's G5-G9, T-051's
inspection) is a chance to re-check whether their recorded status still
holds, since none of them has been revisited specifically for this cycle.

Current status, from `RELEASE_PLAN.md` §3d:
- **T1** (probe-out sentinel): marked unfixed; a loud runtime alert
  (`_probe_out_alert`) covers its first real occurrence instead of fixing
  it. Has **never once fired against real hardware** -- no real recording
  has hit a finger-out moment yet.
- **T2-T7**: fixed, verified against real hardware (patch 0013).
- **T8** (Linux `hid` backend handshake): open, won't-fix for this
  release. Already reconfirmed once this cycle (T-047's 2026-10-21 Linux
  pass: `hidraw` 7/7, `hid` fails consistently, 3/3 retries) -- this
  ticket is about the other seven, not about re-doing T8 again.

What is NOT known:
- Whether any of this cycle's real-device testing (T-047 G5-G9, T-051's
  inspection, a deliberate finger-out moment if one is tried) changes T1's
  status, or any of T2-T7's "still fixed" assumption.

---

## Criteria

- [x] T1: during this cycle's real-device testing, note whether the
      probe-out alert ever fires for the first time (or deliberately try
      a finger-out moment to test it on purpose); record either way.
- [x] T2-T7: spot-checked against this cycle's real-device runs (T-047's
      `info`/`sessions`/`download`), no regression found -- or a
      regression found and filed as its own ticket.
- [x] `RELEASE_PLAN.md` §3d updated with this cycle's re-check results for
      T1-T7 (T8 already updated by T-047).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**T1:** no deliberate finger-out moment tried this cycle; the alert did
not fire on its own during T-047's testing (session 1/2 downloads, no
probe-out samples -- 0 in the G7 CSV pre-check). Staying with the
existing decision (`RELEASE_PLAN.md` §3d): unfixed, mitigation-only,
won't-fix for this release. No further action pursued this cycle.

**T2-T7:** spot-checked via T-047's real-device runs -- `info` and
`sessions` correct (2 real sessions, 160 + 30 records, matching what's
expected), `download` across all four formats clean (0 sequence gaps,
SpO2/HR ranges plausible). No regression found. Still fixed.

`RELEASE_PLAN.md` §3d update still pending.
