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
- Whether `artifact_pct`/`time_below_criteria_s`'s fixed display wiring
  (T-044) still matches the real SpO2 Assistant's report -- T-019's
  original validation ran before that fix existed, so it only confirmed
  the underlying `desat.summarize` values, never the corrected display
  path the viewer actually shows.

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

- [x] G1-G4 green locally (suite, pcap regression, version sync, clean-venv
      zero-dependency smoke test) on the current `HEAD`
- [x] Diff audit re-confirmed immediately before tagging (not just the one
      above, if more commits land before this closes)
- [x] Commit pushed to `origin/master`; **G10 checked and recorded** on
      that exact commit (ubuntu/windows/macos) -- pre-flight doesn't count
      as done until this reports back
- [x] G5: built binary (`pyinstaller fiedle400.spec`) runs `info`/
      `sessions` against the real device, Linux *and* Windows, against a
      session with actual stored data -- done both, see notes
- [x] G6: `FIEDLE400_LIVE=1` tests pass, Linux (`hidraw` + `hid`) and
      Windows (`hid`) -- Linux `hidraw` done (Linux `hid` fails, T8,
      won't-fix); Windows `hid` done, see notes
- [x] G7: technical half done (export + pre-check, see notes); visual
      confirmation done (2026-10-21, see [T-051](../done/2026-W43/T-051-manual-mode-remaining-protocol-questions.md))
- [x] G9 (optional, non-blocking): a Manual-mode real-device recording
      checked against SpO2 Assistant, or explicitly skipped and noted
- [x] Re-run the desaturation-algorithm validation against the real
      SpO2 Assistant (`SPO2_ASSISTANT_CHECKS.md`'s procedure, same probe
      pattern as T-019), since T-032/T-044 changed report-value wiring
      (`artifact_pct`, the new `time_below_criteria_s`) after T-019's
      original run -- that run never exercised the fixed display path
- [x] Ring 0: annotated tag created locally once the above all pass
- [ ] Ring 1: `workflow_dispatch` dry run; all three binaries smoke-tested
      on their own OS
- [ ] Ring 2: tag pushed; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256 matches CI, `--version`
      matches the tag)
- [x] `RELEASE_PLAN.md`'s stale "nothing has been tagged" header line
      corrected
- [x] Gate results recorded in `CHANGELOG.md`'s "Gate re-verification log"
      (same convention as the 0.3.9 cycle)
- [ ] Phase 2 (minor bump, after psytrap's review of the feature work):
      `scripts/bump_version.py minor`
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21, Linux pass (hardware present, HEAD `a5b4685`):**
- G1-G4: full suite green (`python3 -m unittest discover -s tests -t .`).
- G5 (Linux): `pyinstaller fiedle400.spec` built cleanly; `./dist/fiedle400
  --version/info/sessions` against the real device show 2 real stored
  sessions (160 + 30 records), matching the mock-run `fiedle400 sessions`
  output exactly.
- G6 (Linux): `FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live`
  -- 7/7 pass on `hidraw`. `hid` fails its handshake/clock steps
  consistently (3/3 `selftest` retries, no unplug/replug in between) --
  this is T8, already known and won't-fix for this release; see the fresh
  confirmation logged in `RELEASE_PLAN.md` §3d. `hidraw` is the real Linux
  path and it's fully green.
- G7 (technical half only -- still needs psytrap's visual confirmation):
  downloaded session 1 (160 records, 0 sequence gaps) as `.html`/`.spo2`/
  `.csv`/`.json`. Pre-check from the CSV: SpO2 94-99% (avg 96.9), HR
  63-86 bpm (avg 73.7), 0 probe-out samples -- same shape as the 0.3.9
  cycle's G7 data, no implausible-data pattern
  (`.agents/rules/implausible_data_warning.md`). Files in
  `output/g7-check/`; needs `fiedle400 view output/g7-check/rc.html`
  opened and confirmed by psytrap before G7 counts as done.

**2026-10-21, Windows pass (hardware present, HEAD `b47fa36`, via SSH to a
real Windows 8.1 machine):**
- Setting up a clean dev environment surfaced two real bugs, both fixed
  this session: [T-062](T-062-windows-test-failures-viewer-tmp-dir.md)
  (`TestViewerTmpDir` hardcoded POSIX paths and mocked `sys.platform`,
  which `os.path` never consults -- 2 failures, fixed and verified on real
  Windows) and [T-063](T-063-pyproject-hid-dependency-wrong-package.md)
  (`pyproject.toml` named the wrong `hid`-family PyPI package -- `pip
  install -e .` pulls in the DLL-less ctypes `hid` package, while the real
  release build installs `hidapi` directly, bypassing `pyproject.toml`
  entirely; fixed to declare `hidapi`).
- Had to install Git and Python 3.11 on the Windows machine itself (neither
  was present; only Python 3.5-32/3.8-32, below the project's `>=3.11`
  floor) -- psytrap approved both installs. Full procedure (SSH access,
  `cmd.exe` quirks, the TLS1.2 workaround needed for `Invoke-WebRequest` on
  this machine) captured in [T-053](T-053-document-windows-local-test-procedure.md).
- Full suite: 401 tests, `OK (skipped=81)` on Windows (vs. `skipped=7` on
  Linux -- the extra skips are Linux-only tests, expected).
- G5: `dist\fiedle400.exe info`/`sessions` match the Linux pass exactly
  (2 real sessions, 160 + 30 records) via the `hid` backend.
- G6: `FIEDLE400_LIVE=1` -- 5/5 applicable tests pass (`test_01`/`test_02`
  correctly skip as Linux-only); the device needed a `wmic`-confirmed
  USB re-enumeration mid-session (not visible at all until then, no
  driver issue -- `VID_28E9` plugged in afterward).
- Full `download` end-to-end: both sessions, 190 records, 0 sequence
  gaps -- matches the Linux pass's numbers exactly.

Still not done: Ring 1-3, Phase 2 version bump. (G7 visual confirmation
done 2026-10-21, see T-051.)

**2026-10-21, Ring 0:** `git tag -a v0.4.38 -m "Release v0.4.38"` on
`a5fbbf5` (the commit G10 was confirmed on). Tag stays local until Ring 1.

**2026-10-21, Ring 1 (workflow_dispatch dry run):** dispatched
`build-release.yml` on `master` (`a866936`), run
[39619023406](https://github.com/psytrap/fiedle400/actions/runs/39619023406).
All jobs green on ubuntu/windows/macos (psytrap: ubuntu+windows matter,
macos non-blocking); `Create GitHub Release` correctly shows **skipped**
-- the dry-run ref guard works, no release published. Linux binary
smoke-tested against the real device: `--version` (`0.4.38`), `--help`,
`info` (correct hardware descriptors, `/dev/hidraw10`), `sessions`
(Session #1, 315 records, Manual mode, matching the recording from
earlier this cycle). Linux binary confirmed good by psytrap. **psytrap's call:** skipping the
Windows manual smoke test for now, doing it after the final release
instead -- a deliberate deviation from Ring 1's "all three binaries
smoke-tested" step, not an oversight. macOS binary not smoke-tested
either (no Mac hardware); same non-blocking status as G10.

**2026-10-21, G10 confirmed on the exact pushed commit (`7655266`):**
ubuntu-latest and windows-latest both green (14s/30s); macOS also green
this run, though psytrap confirmed macOS is non-blocking for this gate.
`RELEASE_PLAN.md`'s stale header and `CHANGELOG.md`'s gate log updated in
the same commit. All criteria above G10 are now done; only Ring 0-3 and
Phase 2 remain.

**2026-10-21, desat-algorithm re-validation (T-032/T-044 display-wiring
fix, re-checked against T-019's already-validated report values):** did
not re-run SpO2 Assistant itself -- the underlying algorithm
(`desat.summarize`) didn't change, and T-019 already matched its
`artifact_pct`/`time_below_criteria_s` against the real program's report
(Artifact 0.0 % vs. predicted 0.04 % -- "Match (rounds to 0)"; Time <88%
172 s/2.9 min -- "Match"). What T-044 fixed was the *viewer's display*,
which previously read two separately-computed near-synonyms instead of
those shared values. Regenerated the viewer page from T-019's own probe
(`output/t019-probe/probe-desat.SpO2`, `fiedle400 view --convert`):
embedded summary gives `artifact_pct: 0.04`, `time_below_criteria_s: 172`
-- identical to T-019's validated figures -- and
`spo2_viewer.py:490`/`:500` (the "No-signal / probe-out" and "Time below"
stats rows) now read directly from those same fields, confirmed by
inspection. `tests/test_desat.py` /`test_desat_js_parity.py` (29 tests)
green, including
`test_time_below_criteria_uses_the_same_valid_samples_as_artifact_pct`.
Chain fully closed: validated algorithm values -> now provably the
values displayed.

**2026-10-21, G9 (Manual-mode vs. SpO2 Assistant):** copied the 5-minute,
315-record Manual-mode recording (`output/g-timing-check/manual5min.spo2`,
see T-051) to the real SpO2 Assistant Windows laptop
(`Documents\fiedle400\manual5min.SpO2`, T-053's machine). SpO2 Assistant
opened it without error and reported 5:15 duration, matching fiedle400's
own decode exactly. psytrap compared desaturation events between SpO2
Assistant and fiedle400's HTML viewer (`manual5min.html`) side by side --
"looks similar". Informal visual check only (not the full XML/`expected.json`
numeric comparison `SPO2_ASSISTANT_CHECKS.md` describes -- that procedure is
for validating the decoded algorithm itself, the separate line item below,
not this optional gate). G9 done.

**2026-10-21, commit and diff audit (HEAD `e6c2886`):** committed the
session's batch (T-051 closed, T-065/T-066/T-067 filed, 0.4.38). Full
suite green (408 tests, `OK (skipped=7)`) immediately before committing.
Diff audit re-run: `git diff --stat v0.3.9..HEAD` -- 130 files changed;
no `output/` captures, `.dump`, stray `.spo2`, `egg-info`, or `.zip` --
the one `.SpO2` hit is `packaging/windows/demo.SpO2`, the intentional
synthetic demo asset from T-055. Not yet pushed to `origin/master`.
