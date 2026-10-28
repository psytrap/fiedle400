# T-096: Ship the next release (v0.5.x) -- re-run the Runbook Checklist

- **Status:** Open
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `RELEASE_PLAN.md` §2 (gates), §4 (rollout rings), §6 (runbook checklist
    -- this ticket is that checklist, instantiated for this cycle)
  - `fiedle400/__init__.py`, `pyproject.toml` (version)
  - `.github/workflows/tests.yml`, `.github/workflows/build-release.yml`
  - `CHANGELOG.md` (record the gate re-verifications here as they happen,
    same as prior cycles)

---

## Description & Context

Nothing has shipped since `v0.4.41` (tagged and released; see
[T-047](../done/2026-W43/T-047-release-v0-4.md)). `master` is now at
`0.5.0` -- [T-079](../done/2026-W44/T-079-final-beta-testing-before-phase-2.md)
closed out the beta-testing phase and ran the Phase 2 minor bump
(`0.4.43 -> 0.5.0`), per psytrap's explicit confirmation ("t79 is
complete... lots of long recordings with some findings").

**What changed since `v0.4.41`, in gate-relevant terms:** T-086 (desat.py
rename/cleanup), T-087 (session-count mismatch fix), T-084 (checksum
failures on long downloads, conditional idle-sleep), T-088 (opt-in
background HID reader thread), T-089 (`wait_for_packet()`, session
list/RTC read migration, `_erase_status()` redesign), T-090 (unified
`_flush_before_command()`), T-092 (`clear_memory()` no longer
early-returns before touching the device), T-083 (Arduino+servo test
fixture confirmed working), T-081 (backlog grouping, process-only,
no code impact), and **T-094** (Manual-mode download of a long
recording losing 97-100% of its samples -- a serious real-hardware
finding, root-caused and fixed, confirmed with a 10x full-length
re-download: byte-for-byte identical, 0 missing samples across all 10
runs).

**Diff audit (§1), not yet run for this cycle:**
`git diff --stat v0.4.41..HEAD` -- 53 files changed as of `210a7d6`; not
yet checked for debris (`output/`, `.dump`/`.spo2` captures, `egg-info`,
`.zip`).

**Open release blockers:** none currently in `tickets/INDEX.md`'s main
table besides this ticket itself and
[T-095](T-095-beta-rollout-advertise-and-find-users.md) (beta-rollout
advertising, not release-blocking, details TBD).

**What is NOT known yet:**
- Whether G5/G6 (real hardware, Linux + Windows) still pass after this
  much change -- not re-run since the `v0.4.41` cycle's verification.
  T-094's fix was validated against real hardware during its own work,
  but that was targeted (Manual-mode download specifically), not a full
  G5/G6 pass.
- Whether a Windows laptop run is feasible this cycle.

## Criteria

Taken directly from `RELEASE_PLAN.md` §6, scoped to this cycle:

- [ ] G1-G4 green locally (suite, pcap regression, version sync,
      clean-venv zero-dependency smoke test) on the current `HEAD`
- [ ] Diff audit (`git diff --stat v0.4.41..HEAD`) -- zero debris
- [ ] Commit pushed to `origin/master`; G10 checked and recorded on that
      exact commit
- [ ] G5: built binary (`pyinstaller fiedle400.spec`) runs `info`/
      `sessions` against the real device, Linux *and* Windows
- [ ] G6: `FIEDLE400_LIVE=1` tests pass, Linux (`hidraw` + `hid`) and
      Windows (`hid`)
- [ ] G7: visual acknowledgment (`fiedle400 view`)
- [ ] Ring 0: annotated tag created locally once the above all pass
- [ ] Ring 1: `workflow_dispatch` dry run; all three binaries
      smoke-tested on their own OS
- [ ] Ring 2: tag pushed; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256 matches CI, `--version`
      matches the tag)
- [ ] Gate results recorded in `CHANGELOG.md`'s "Gate re-verification log"
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

(Not started.)
