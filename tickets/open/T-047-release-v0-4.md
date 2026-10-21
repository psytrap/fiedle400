# T-047: Ship the next release (v0.4.x) -- re-run the Runbook Checklist

- **Status:** Open
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `RELEASE_PLAN.md` §2 (gates), §4 (rollout rings), §6 (runbook checklist
    -- this ticket is that checklist, instantiated for this cycle)
  - `fiedle400/__init__.py`, `pyproject.toml` (version)
  - `.github/workflows/tests.yml`, `.github/workflows/build-release.yml`
  - `CHANGELOG.md` (record the gate re-verifications here as they happen,
    same as the 0.3.9 cycle did)

---

## Description & Context

Nothing has shipped since `v0.3.9` (tagged and released 2026-10-16,
confirmed beta: `git ls-remote --tags origin` shows it on GitHub, Ring 3.1
done per `RELEASE_PLAN.md` §4). `master` is currently **62 commits ahead
of `origin/master`**, at version `0.4.30` (built up by many free patch
bumps across many closed tickets, per the 2026-10-15 "patch-bump freely"
rule -- not a sign anything is wrong, just that no cycle has closed since).
`RELEASE_PLAN.md`'s own header line ("Nothing has been tagged or
released") is stale and should be corrected as part of this ticket's docs
pass; the tag history contradicts it.

**What changed since v0.3.9, in gate-relevant terms:**
- The HTML viewer became the default download output and `fiedle400 plot`
  (and the matplotlib dependency) was removed entirely (T-006/T-012/T-013,
  0.4.26) -- this changes what G4 (zero-dependency promise) and G7 (visual
  acknowledgment) actually exercise: G7 is now `fiedle400 view`, not a PNG.
- `fiedle400 clear` now sends the vendor's own `9D 7F` erase commands
  instead of an unverified byte sequence (T-037, T-038).
- Manual-mode recordings are implemented (T-042, 0.4.28) -- new code path
  with no real-device run yet (see Open questions below).
- The desaturation-event algorithm was reviewed against the decoded spec;
  two display-layer discrepancies found and fixed (T-032, T-044, 0.4.30).
- Pulse-rate desaturation detection implemented and decoded (T-029/T-030).
- `SPO2_FORMAT.md`/`PROTOCOL.md` substantially corrected (byte 2/3 of the
  `0xEC` header renamed from "user"/"session" to "user"/"entry", T-039;
  the single-pass description of the detector added).

**Diff audit (§1) already run for this cycle:**
`git diff --stat v0.3.9..HEAD` -- 100 files changed, clean: no
`output/` files, `.dump`/`.spo2` captures, `egg-info`, or `.zip` in the
diff.

**No open release blockers.** `tickets/INDEX.md`'s main table is empty;
everything else is closed or explicitly deferred (T-021/023/024/035/040/
041/043/045/046). T1 and T8 (`RELEASE_PLAN.md` §3d) remain won't-fix for
this release, as already decided. The two local-only checks already
tracked in `tickets/INDEX.md`'s "Open questions" (`fiedle400 clear` on a
real device, Manual mode on a real device) are this cycle's G5/G6/G9 work,
not separate from it -- doing them *is* most of what's left below.

**What is NOT known:**
- Whether G5/G6 (real hardware, Linux + Windows) still pass after this
  much change -- not re-run since 0.3.9's verification.
- Whether a Windows laptop run is feasible this cycle (G6 needs it for
  the `hid` backend; D4's minimum-Windows claim was verified at 0.3.9 and
  hasn't been re-checked since).
- Whether a Manual-mode real-device recording is available this cycle for
  G9 (optional, non-blocking either way).

**Named CI/workflow debt, checked against the actual workflow files on
2026-10-21, deliberately not made part of this release:** `ubuntu-latest`
now meaning Ubuntu 26 (the 2026-10-19 cutover already passed), the Actions
Node 20 deprecation warnings' current status, and the untested macOS
Gatekeeper/quarantine path. None of them block v0.4.x shipping as-is; spun
off as [T-049](T-049-ci-workflow-debt.md) (deferred). Likewise the
`builtins.input`-vs-pty question from the same `RELEASE_PLAN.md` section,
which has no known bug behind it: [T-048](T-048-pty-input-mocking-review.md)
(deferred).

---

## Criteria

Taken directly from `RELEASE_PLAN.md` §6, scoped to this cycle:

- [ ] G1-G4 green locally (suite, pcap regression, version sync, clean-venv
      zero-dependency smoke test) on the current `HEAD`
- [ ] Diff audit re-confirmed immediately before tagging (not just the one
      above, if more commits land before this closes)
- [ ] Commit pushed to `origin/master`; **G10 checked and recorded** on
      that exact commit (ubuntu/windows/macos) -- pre-flight doesn't count
      as done until this reports back
- [ ] G5: built binary (`pyinstaller fiedle400.spec`) runs `info`/
      `sessions` against the real device, Linux *and* Windows, against a
      session with actual stored data
- [ ] G6: `FIEDLE400_LIVE=1` tests pass, Linux (`hidraw` + `hid`) and
      Windows (`hid`)
- [ ] G7: a real-finger session downloaded and opened with
      `fiedle400 view`; psytrap confirms the chart looks physiologically
      plausible (per `.agents/rules/implausible_data_warning.md`)
- [ ] G9 (optional, non-blocking): a Manual-mode real-device recording
      checked against SpO2 Assistant, or explicitly skipped and noted
- [ ] Ring 0: annotated tag created locally once the above all pass
- [ ] Ring 1: `workflow_dispatch` dry run; all three binaries smoke-tested
      on their own OS
- [ ] Ring 2: tag pushed; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256 matches CI, `--version`
      matches the tag)
- [ ] `RELEASE_PLAN.md`'s stale "nothing has been tagged" header line
      corrected
- [ ] Gate results recorded in `CHANGELOG.md`'s "Gate re-verification log"
      (same convention as the 0.3.9 cycle)
- [ ] Phase 2 (minor bump, after psytrap's review of the feature work):
      `scripts/bump_version.py minor`
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
