# T-096: Ship the next release (v0.5.x) -- re-run the Runbook Checklist

- **Status:** Done
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

- [x] G1-G4 green locally (suite, pcap regression, version sync,
      clean-venv zero-dependency smoke test) on the current `HEAD`
- [x] Diff audit (`git diff --stat v0.4.41..HEAD`) -- zero debris
- [x] Commit pushed to `origin/master`; G10 checked and recorded on that
      exact commit
- [x] G5: built binary (`pyinstaller fiedle400.spec`) runs `info`/
      `sessions` against the real device, Linux *and* Windows
- [x] G6: `FIEDLE400_LIVE=1` tests pass, Linux (`hidraw` + `hid`) and
      Windows (`hid`)
- [x] G7: visual acknowledgment (`fiedle400 view`)
- [x] Ring 0: annotated tag created locally once the above all pass
- [x] Ring 1: `workflow_dispatch` dry run; all three binaries
      smoke-tested on their own OS
- [x] Ring 2: tag pushed; GitHub Release published
- [x] Ring 3: published assets verified (SHA-256 matches CI, `--version`
      matches the tag)
- [x] Gate results recorded in `CHANGELOG.md`'s "Gate re-verification log"
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

**2026-10-28 (Claude): G1-G4 and diff audit done, `HEAD` = `ece8626`.**
- G1 (full mock suite): `python3 -m unittest discover -s tests -t .` --
  423 tests, OK (skipped=7, the opt-in live-device tests).
- G2 (pcap regression): included in the G1 run above (`test_pcap_decoder`
  runs, does not skip).
- G3 (version sync): `python3 -m unittest tests.test_version -v` --
  9/9 OK.
- G4 (zero-dependency smoke test): fresh venv, `pip list` shows only
  `pip` itself. `python -m fiedle400 --version` -> `fiedle400 0.5.0`;
  `--help`, `info`, `sessions`, `download --help`, `view --help` all
  import and run (no `ImportError`; `info`/`sessions` correctly report
  "No Pulsox PO-400 device found" since no hardware was attached for
  this check -- see below); confirmed no `matplotlib` module ends up in
  `sys.modules`.
- Diff audit: `git diff --stat v0.4.41..HEAD` -- 55 files changed,
  3575(+)/578(-); `git diff --name-only v0.4.41..HEAD` grepped for
  `.dump`/`.spo2`/`.zip`/`egg-info`/`/output/`/`.html` -- zero matches.
  `git status --short --untracked-files=all` on the working tree is
  also empty.

**Blocked on hardware right now:** `lsusb` shows no PO-400 attached at
the moment (device not plugged in during this session) -- G5 (real
hardware via the built binary) and G6 (`FIEDLE400_LIVE=1` tests) can't
be run until it's connected. G7 (visual `fiedle400 view` acknowledgment)
also needs a real downloaded recording. Picking these up once the
device is plugged back in.

**2026-10-28 (Claude), device reconnected with a fresh test session --
G5/G6/G7 done on Linux.** psytrap plugged the device back in and
recorded a fresh session (`fiedle400 sessions`: Session #1, 454
records, 7m34s, 2026-10-28 08:31:43) -- the prior long Manual-mode
recording used for T-094 is no longer on the device (presumably erased
between sessions; not investigated further, not a release blocker).

- G5: `dist/fiedle400 info` -- connects, reports v0.5.0 standalone
  binary, `Linux hidraw (native)` backend, correct hardware model.
  `dist/fiedle400 sessions` -- lists the session correctly.
  `dist/fiedle400 download -s 1 -o t096_session1.json` -- 454/454
  records, 539 packets, **0 sequence gaps**. Linux confirmed; Windows
  still not run this cycle (no Windows machine available right now --
  tracked as open in "What is NOT known yet" below, same caveat the
  ticket already called out).
- G6: `FIEDLE400_LIVE=1 FIEDLE400_HID_BACKEND=hidraw python3 -m
  unittest discover -s tests -t .` -- 423 tests, OK (skipped=1, so 6
  live-device tests actually ran). Repeated with
  `FIEDLE400_HID_BACKEND=hid` -- same result, 423 OK, skipped=1. Both
  Linux backends green. Windows (`hid`) still pending, same caveat.
- G7: `dist/fiedle400 view t096_session1.json --convert -o
  t096_view.html` -- generated a 62 KB viewer page; opened it in a
  browser (served over local HTTP since it's outside the project dir)
  and visually confirmed: SpO2 (99% flat) and heart-rate (38-41 bpm)
  traces both render over the full 7m34s span, duration/min/avg/max
  stats table populated correctly, desaturation- and pulse-rate-event
  analysis sections both present and showing 0 events (consistent with
  a short, stable test recording), and the event-threshold input boxes
  all render with their current default values. No rendering glitches,
  no console-visible errors in the page itself.

**2026-10-28 (Claude), Windows leg of G5/G6 done via SSH to
`192.168.2.165` (psytrap moved the PO-400 to the Windows machine for
this).**

- Repo at `C:\Users\mik\fiedle400-repo` was stale (pinned at the old
  T-047 commit); `git pull origin master` fast-forwarded it to
  `ece8626`, matching the Linux `HEAD` used for the rest of this
  ticket. Working tree was clean before the pull (no local changes
  lost).
- Python: the machine's default `python` resolves to a Python 3.5
  install (too old -- f-strings in the test suite raise `SyntaxError`
  on import). Used `py -3.11` (also present) for everything instead.
- First `hid`-backend attempt failed: `pip install hid` had pulled in
  the wrong PyPI package (the ctypes-based `hid` 1.0.9, which needs a
  separate system `hidapi.dll` that wasn't present) and clobbered the
  correct one. `pyproject.toml` actually wants `hidapi` (cython-hidapi,
  which also provides the `import hid` name and bundles its own
  compiled extension). Fixed with `pip uninstall hid` +
  `pip install --force-reinstall hidapi` -- `import hid` then worked
  with no missing-DLL error.
- G5: `py -3.11 -m PyInstaller fiedle400.spec --noconfirm` built
  `dist\fiedle400.exe` cleanly. `--version` -> `fiedle400 0.5.0`;
  `info` -> connects via `hid (cross-platform)` backend, correct
  device descriptors; `sessions` -> lists the one stored session (454
  records, 7m34s -- same session used for the Linux G5/G7 checks,
  since psytrap physically moved the device rather than recording a
  new one); `download -s 1 -o ...` -> **454/454 records, 539 packets,
  0 sequence gaps**.
- G6: `FIEDLE400_LIVE=1 py -3.11 -m unittest discover -s tests -t .`
  -- first attempt silently ran as the *mock* suite (423 OK,
  skipped=87, unchanged from the non-live run) because `set
  FIEDLE400_LIVE=1 && ...` on a single cmd.exe line sets the variable
  to `"1 "` (trailing space included, a cmd.exe parsing quirk) and
  `tests/test_device_live.py`'s gate is an exact `== "1"` comparison.
  Fixed by quoting the assignment (`set "FIEDLE400_LIVE=1" && ...`),
  which sets it to a clean `"1"`. Re-ran: **423 tests, OK, skipped=83**
  (down from 87 -- the 4 live-hardware-gated tests that don't depend on
  a Linux-only backend ran for real against the Windows-attached
  device; the Linux-hidraw-only tests and the Node-parity tests remain
  correctly skipped on this platform).
- Mechanical note for next cycle: G1-G4 were also re-run on Windows as
  a sanity check before G5/G6 (not strictly required since Linux
  already covers them, but cheap given the SSH session was already
  open) -- 423 tests, OK, skipped=87 (the Windows-platform baseline:
  Linux-hidraw-only tests + Node-parity tests + live-device tests, all
  correctly skipped without `FIEDLE400_LIVE`).

**2026-10-28 (Claude): G10 checked on `ece8626`.** `gh run view
40643539388` -- `headSha` = `ece86268188312efa9c9e10a720daa749ad1f424`
(matches `HEAD`), conclusion `success` on all three legs:
`ubuntu-latest`, `windows-latest`, `macos-latest` (Python 3.11).
[Run 40643539388](https://github.com/psytrap/fiedle400/actions/runs/40643539388).

**psytrap plans an additional ~8h real-recording reliability test on
the Windows machine before tagging** -- a longer, more realistic
Windows-side exercise of the download path (beyond this cycle's
454-record/7m34s smoke test) on top of the 10x full-length Linux
confirmation already done for T-094. Not yet run; holding Ring 0
(local tag) until that's back.

**2026-10-28, psytrap: "Fine Windows works with 9 hour recording and
erases."** The planned long-recording test ended up being ~9h (longer
than the ~8h originally planned) and also exercised erase, not just
download -- both confirmed working on the Windows machine with the
0.5.0 build installed earlier in this cycle. Exact record count/
sequence-gap numbers not captured here (psytrap ran it directly, not
through this session) -- taken at psytrap's word per their report,
consistent with the 10x full-length Linux confirmation already done
for T-094 and this cycle's own Windows G5/G6 smoke tests. This clears
the hold on Ring 0.

**2026-10-28 (Claude): Ring 0 and Ring 1 done.**
- Ring 0: `git tag -a v0.5.0 -m "Release v0.5.0"` on `ece8626` (local
  only, not pushed yet).
- Ring 1: `gh workflow run build-release.yml --ref master` -- dispatched
  dry run, [run 40713552179](https://github.com/psytrap/fiedle400/actions/runs/40713552179).
  First attempt: `Build macos (arm64)` queued for ~15 min then came
  back `cancelled` (GitHub macOS-runner capacity, not something in the
  repo -- the `Test` job for macOS had already passed fine in the same
  run). `gh run rerun --failed` re-ran just that job; second attempt
  green. Final state: all three `Test` jobs, all three `Build` jobs,
  and the `Windows Installer` job all `success`; `Create GitHub
  Release` correctly `skipped` (no tag pushed, so the dry-run ref
  guard works as designed). Artifact sizes sane: linux 18.1 MB (tar.gz),
  windows 8.3 MB (portable exe), windows installer 9.8 MB, macos
  8.3 MB.
- Downloaded the linux and windows portable artifacts and smoke-tested
  by hand: `fiedle400-linux-x64.tar.gz` (extracted) -- `--version` ->
  `fiedle400 0.5.0`, `--help` prints correctly; real-device `info`
  check skipped here since the PO-400 was on the Windows machine at
  the time (already exhaustively exercised against real hardware this
  cycle via G5/G6's separately-built binaries, so not re-litigated).
  `fiedle400-windows-x64.exe` (copied to the Windows machine via scp)
  -- `--version` -> `fiedle400 0.5.0`, `--help` exits 0 and prints
  correctly; `info` correctly reports no device found (PO-400 had been
  unplugged from the Windows machine after psytrap's 9h test). macOS:
  no Mac available to hand-smoke-test, same as every prior cycle
  (RELEASE_PLAN.md D2) -- the `Test macos-latest` CI job passing is the
  gate for it.

**2026-10-28 (Claude): Ring 2-3 done, ticket complete.**
- Ring 2: `git push origin v0.5.0` triggered
  [40717598236](https://github.com/psytrap/fiedle400/actions/runs/40717598236)
  -- all `Test`/`Build`/`Windows Installer` jobs green, `Create GitHub
  Release` succeeded. Published:
  <https://github.com/psytrap/fiedle400/releases/tag/v0.5.0> with all
  four assets (`fiedle400-linux-x64.tar.gz`, `fiedle400-windows-x64.exe`,
  `fiedle400-setup.exe`, `fiedle400-macos-arm64`).
- Ring 3: downloaded all four assets from the Release page and from the
  CI run's artifacts; `sha256sum` on each pair matches byte-for-byte.
  Extracted the Linux asset and ran `--version` -> `fiedle400 0.5.0`,
  matching the tag.
- Full gate re-verification log entry written to `CHANGELOG.md`'s "Gate
  re-verification log" section (`0.5.0` entry, mirrors the `0.4.41`
  entry's structure).

Full v0.5.0 runbook complete: G1-G7, diff audit, G10, Ring 0-3, and
CHANGELOG all done. [T-097](T-097-windows-installer-upgrade-over-existing-install.md)
spun off separately for the one gap noticed along the way (the real
Inno Setup installer's upgrade-over-existing-install path wasn't
exercised this cycle -- a manual uninstall+copy stood in for it on the
Windows machine since `ISCC.exe` isn't installed there).
