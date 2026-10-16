# fiedle400: Test & Release Plan

> **Scope:** First tagged release of the `fiedle400` CLI (GitHub Release with Linux, Windows and macOS binaries)
> **Cadence:** Two-Phase Version Bump (Patch Pre-Flight • Minor Post-Shipment), adapted from the RefDiff rollout plan
> **Baseline:** see `fiedle400/__init__.py` for the current version (patch-bumped freely per §1's rule; no git tags exist yet)
> **Status:** Strategy approved by psytrap (2026-10-15). All blockers B1–B7 resolved. The `fiedle400` rename (§3b, patch 0010) has landed. All findings T1-T7 (§3d) are **fixed in patch 0013 and verified against the real device** -- not just the simulator: `sessions`/`download` on the real PO-400 now correctly show 107 records / 1m 47s (was 214 / 4m 03s), and `info` honestly reports fields the device never answers instead of inventing them. A new finding, T8, was found afterward (Linux `hid`/libusb backend). `fiedle400 selftest` (new) gives a one-command, read-only hardware check with no env var needed. Nothing has been tagged or released.
> **Workflow:** Changes are made and unit/mock-tested in the cloud copy (`/mnt/project-files/po400`); psytrap applies the patches locally, runs the live gates (G5–G7) and pushes to the private remote `github.com/psytrap/fiedle400`, where CI (`tests.yml`) runs on every push and PR.

---

## 1. Version Strategy (Two-Phase Bump)

The bump strategy is taken from the RefDiff plan and adapted to a Python package:

| Phase | When | Command | Effect |
|:---|:---|:---|:---|
| **0. Reconcile** ✅ | Once, before the first release | `python3 scripts/bump_version.py set 0.1.0` | Done: both manifests now say `0.1.0` (`__init__.py` was `2.0.0`). |
| **1. Pre-Flight (Patch)** | Start of every release cycle, **exactly once** | `python3 scripts/bump_version.py patch` | `0.1.0 → 0.1.1`. This is the release candidate that gets tested, tagged and shipped. No feature bumps during pre-flight. |
| **2. Post-Shipment (Feature)** | Final step, **only after** pre-flight passed, the GitHub Release is verified live (§4 Ring 3), and the feature work has been reviewed by the user | `python3 scripts/bump_version.py minor` (or `major`) | `0.1.1 → 0.2.0`. Records the shipped milestone on `master`. The next cycle's pre-flight patch then produces `0.2.1`. |

**Rules**
- **Single source of truth.** The version lives in `pyproject.toml` (`[project].version`) and `fiedle400/__init__.py` (`__version__`). `bump_version.py` rewrites both, and a test asserts they match (§2, G3).
- **Patch-bump freely (psytrap, 2026-10-15).** Bump the patch version at any point, as often as useful -- there is no one-bump-per-cycle limit. Every change that produces a different artifact should carry a different version, so a tested build and an untested one are never both called the same thing. Minor and major bumps keep their Phase 2 rules below.
- **Small, focused diffs between bumps.** No monolithic changes; each blocker fix (§3) is its own commit.
- **Diff audit before every tag:** `git diff --stat v<prev>..HEAD && git diff v<prev>..HEAD`, which should show zero debris: no `output/` files, `.dump` or `.spo2` captures, `egg-info`, or `fiedle400.zip`. For the first release, audit against the initial commit.

**`major` vs `minor`:** use `major` only for a breaking CLI change (renamed subcommands or flags, a changed default output format or location). Everything else uses `minor`.

---

## 2. Pre-Flight Quality Gates

All gates must pass on the patch-bumped RC before tagging.

```bash
python3 scripts/bump_version.py patch                      # Phase 1: once per cycle
git diff --stat && git diff                                # Diff audit: zero debris
python3 -m unittest discover -s tests -t . -v             # G1/G2: full mock suite
python3 -m fiedle400 --version && python3 -m fiedle400 --help      # G4: stdlib-only smoke test (no matplotlib)
pyinstaller fiedle400.spec && ./dist/fiedle400 --version && ./dist/fiedle400 info   # G5: built binary must reach the device (local only)
FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live -v  # G6: live hardware, both backends (opt-in)
fiedle400 selftest                                          # quick one-off hardware check, no env var needed
fiedle400 download -o output/rc.spo2 && fiedle400 plot output/rc.spo2   # G7: visual acknowledgment
```

| Gate | Check | Today |
|:---|:---|:---|
| **G1 Mock suite** | `python3 -m unittest discover tests`: 0 failures, 0 errors. The only skips allowed are the 7 opt-in live-device tests (plus the plot tests when matplotlib is absent); the count must not vary with device state. | ✅ 157 run / 7 skip (live device only) with matplotlib, after patches 0005–0007. |
| **G2 Capture regression** | `test_pcap_decoder` actually runs against `analysis/bum400_20260906_100516.pcap` (it must not skip). | ✅ Runs and passes (B2). |
| **G3 Version sync** | `tests/test_version.py`: `fiedle400.__version__` equals `pyproject.toml` version; `fiedle400 --version` prints it; bump script cycle works. | ✅ Passing. |
| **G4 Zero-dependency promise** | In a clean venv with no third-party packages, `python3 -m fiedle400 --help`, `info`, `sessions` and `download` import and run. `plot` prints an install hint and exits 1. | ✅ Verified in a clean venv: 107 tests run, 0 failures (plot tests skip). |
| **G5 Binary build** *(local only)* | `pyinstaller fiedle400.spec` succeeds, **and the built artifact runs a device-touching command** (`info`, then `sessions`) with a real PO-400 attached; for Windows, the installed binary from the installer. `--version`/`--help` alone are not enough: a binary that starts but cannot load the `hid` extension passes them (this happened before `0ab3bf0`). CI runners have no oximeter, so this gate can only run on psytrap's machines; CI only proves the build succeeds. | ✅ `fiedle400-setup.exe` from CI, freshly installed on the Windows 8.1 laptop at `0.1.11`: `info`/`sessions` against the real device both correct post-T1-T7 fix (107 records, 1m 47s; "not reported by the device" where the device genuinely gives nothing). Re-run on each RC build -- this run does not carry forward to the next version. |
| **G6 Live hardware** *(mandatory, the analogue of RefDiff's live CDP invariant)* | `FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live` passes with a real PO-400 attached, on Linux with **both** backends (`hidraw` and `hid`); elsewhere with `hid` only (`hidraw` raises off Linux by design, and the Linux-only tests skip with a reason). Never run two live runs at once (a lock file serialises them). `fiedle400 selftest` runs the same core checks with no env var, for a quick one-off. | ✅ Linux `hidraw`: 5/5 pass at `0.1.11` (device detection, connect, handshake, RTC, sessions). Windows `hid`: 5/5 pass on the laptop (same run as G5). ⚠️ Linux `hid` backend: **new finding T8** (below) -- connects, but the session query returns a bare ACK instead of data on this machine's libusb-backed install; not yet root-caused. |
| **G7 Visual & data acknowledgment** | Record a short session **with a finger on the probe**, download it to `.spo2`, `.csv` and `.json`, run `fiedle400 plot`, and have the user confirm the PNG looks physiologically plausible. Per `.agents/rules/implausible_data_warning.md`, constant 95/64 or 99/95 values with probe-out flags fail this gate. | ✅ **Passed (psytrap, 2026-10-15).** Two real sessions (92 records/1m32s and 937 records/~15.5min) plotted and confirmed plausible: SpO2 92-99%, HR 49-81, real variation, no flat-line pattern. This is the **beta** criterion (§3f); with G7 passed and no other gate blocking, this release is ready to promote from alpha. |
| **G8 Output location** | Per `AGENTS.md`, output goes to the current directory (or the configured workdir), never a hard-coded `output/`; help strings say the same. | ✅ The code always wrote to the cwd; only the help strings said `output/`. Fixed in `9647913`. |

> [!WARNING]
> **Process gap, v0.2.17 / 0.3.0 cycle (psytrap, 2026-10-15): G5/G6 were
> not actually satisfied before shipping, and a same-day retroactive check
> did not close it either.** The cycle was tagged and released on doc-only
> changes without re-running the real-hardware gates first. A same-day
> catch-up run (`info`/`sessions` against the real shipped binary, plus
> `FIEDLE400_LIVE=1` tests) only proved: Linux `hidraw` connect, handshake,
> RTC, and an *empty* session query all still work. It did **not** cover:
> (a) **Windows** -- no run on the laptop happened this cycle at all, and
> nothing here can substitute for one; (b) **real stored data** -- the
> device currently holds zero sessions (erased by this session's own
> Manual-mode testing), so `download` against an actual multi-record
> session -- the part T6/T7/the storage decoder exist to protect -- was not
> exercised, on either platform. G5/G6 for this cycle should be treated as
> **not done**, not as retroactively passed. Closing this needs: a real
> Manual *and* Auto-mode recording with actual data on the device, and a
> run of `fiedle400 selftest` (or the fuller G5/G6 commands above) on both
> Linux and the Windows laptop against that data -- not something that can
> be completed from here alone.

---

## 3. Release Blockers (fix before Phase 1)

Each blocker is a small, separate commit, landed **before** the patch bump.

| ID | Problem | Evidence | Fix |
|:---|:---|:---|:---|
| **B1** ✅ | matplotlib is a hidden hard dependency | `fiedle400/__init__.py:15` imports `plot` eagerly, so every `from fiedle400 import ...` (including `cli.py:24`) pulls in matplotlib. `cli.py:42` already imports `plot` lazily, so the eager import defeats that. | Done: `plot_session` is resolved lazily via `__getattr__`; `plot = ["matplotlib"]` extra added; `fiedle400 plot` prints an install hint when matplotlib is missing. |
| **B1b** ✅ | The release binary would crash on start | `.github/workflows/build-release.yml` installs only `pyinstaller hidapi`. Because of B1, the frozen binary would raise `ImportError` on every command (inferred, not yet built). | Fixed by B1. **Decision superseded (psytrap, 2026-10-15): matplotlib IS now bundled.** The original call was "plot is not shipped in the binary" (`fiedle400.spec` excluded it); reversed after measuring the real cost -- same build environment, same version: 8.8 MB without matplotlib, 44.0 MB with it, **+35.2 MB (~5x)**, confirmed working (`--version`, `plot --help`) before accepting it. `excludes=[]` now; `build-release.yml` installs `matplotlib` alongside `pyinstaller hidapi` for all three OS legs. G4 (clean-venv, stdlib-only) is unaffected -- that gate is about running from source, not the frozen binary, and still requires `plot` to print its install hint there. **Graceful failure (psytrap):** every command now runs through `cli.run_guarded`, which turns unexpected errors into a one-line message and exit code 1 (Ctrl+C → 130); `FIEDLE400_DEBUG=1` shows the full traceback. |
| **B2** ✅ | The pcap regression test never runs | `tests/test_pcap_decoder.py` imports `capture.decode_pcap`, but the module is at `archive/capture/` (and `archive/` is git-ignored). | Done: decoders copied to `tests/capture_tools/` (tracked); the pcap fixture in `analysis/` was already tracked. This also fixes `test_export_spo2.py`, which imported `decode_spo2` from the git-ignored `archive/` and would have failed on a fresh clone or in CI. |
| **B2b** ✅ | The pcap decoder reads byte order backwards | `archive/capture/decode_pcap.py:73` treats a file starting with `d4 c3 b2 a1` as big-endian. It is little-endian, so 0 reports are parsed. | Done in `tests/capture_tools/decode_pcap.py` (274 reports, 244 samples); a test pins the little-endian case. |
| **B2c** ✅ | The test expects 2 sessions; the capture has 1 | After B2b: one `0xEC` frame, session 1, 243 records, 4m 03s. | The test was wrong: `analysis/bum400_20260906_100516.md` (frame 067) shows one `0xEC` header with 243 samples. The test now expects 1 session, id 1, 243 records. Open observation: the notes say 243 samples ≈ 122 s, while `duration_str` reports 4m 03s. |
| **B3** ✅ | Version drift and no `--version` | See G3. | Done: `scripts/bump_version.py` (`show`, `set`, `patch`, `minor`, `major`; refuses to bump when manifests disagree), `fiedle400 --version`, `tests/test_version.py`. |
| **B4** ✅ | The release workflow doesn't test | `build-release.yml` builds on tag push with no test step. | Done: `test` job on ubuntu, windows and macos (Python 3.11) runs the suite stdlib-only (G4), then again with matplotlib (G1/G2); `build` has `needs: test`; on tag pushes the job fails unless `v<__version__>` equals the tag. |
| **B5** ✅ | Stale build metadata | `fiedle400.spec` hidden imports omitted `fiedle400.export`. | Spec hidden imports: `fiedle400.export` added in 0001. (`fiedle400.egg-info/` is untracked, so it was never an issue in git.) |
| **B6** ✅ | Docs point at a local machine | README, DESIGN.md and PROTOCOL.md used `file:///home/mik/...` links. | Done: all links are relative (README in 0002, the other two locally). |
| **B7** ✅ | Windows console encoding | Emoji and box characters raised `UnicodeEncodeError` on a legacy-codepage Windows console (cp850) (`handoff/windows-console-encoding.md`). | Fixed locally: output falls back to ASCII replacements instead of crashing. |

---

## 3b. Rename the tool to `fiedle400` (patch 0010)

Decided by psytrap (2026-10-15): **apply after tagging `v0.1.1`**, so the release
that ships is the hardware-tested `po400` build. The rename then opens the next
cycle and goes through G1–G6 again on that cycle's RC. The device is still the
**PO-400**: only the tool is renamed.

**What actually happened:** `v0.1.1` was never tagged -- nothing has been
tagged at all -- so the rename landed directly on `master` instead of after a
tag. No release shipped under the `po400` name. The "re-run G1-G6 on the next
RC" intent still holds and is why G5/G6 above were re-verified at `0.1.11`.

| Area | Renamed | Kept as is |
|:---|:---|:---|
| Package, entry point | `fiedle400/`, `fiedle400` command, `python -m fiedle400`, `prog` names | |
| Packaging, CI | `fiedle400.spec`, `fiedle400.bat`, `packaging/windows/fiedle400.iss`, release asset names | |
| Settings | `%APPDATA%\fiedle400`, `$XDG_CONFIG_HOME/fiedle400` | An existing `po400/config.json` is copied over on first read; the old file stays. |
| Env vars | `FIEDLE400_LIVE`, `FIEDLE400_DEBUG`, `FIEDLE400_WORKDIR` | The `PO400_*` names still work when the new ones are unset. |
| Installer | App name `fiedle400 (PO-400 Oximeter)`, folder `Programs\fiedle400` | Same `AppId`, so it **upgrades** a po400 install: it removes the old program folder and context-menu keys. Start Menu shortcut "PO-400 Oximeter" and `Documents\PO-400` stay. |
| Device-facing names | `po400_…` recording filenames -> `fiedle400_…` (done separately after this patch) | "PO-400" in docs and output (the device's own name), udev rule filenames, `analysis/`, `handoff/` history |

---

## 3c. Decisions (psytrap, 2026-10-15)

| # | Decision | Status |
|:--|:---|:---|
| **D1 Code signing** | **Won't fix.** Binaries ship unsigned. | Release notes tell users how to get past the SmartScreen warning and to verify the SHA-256. Revisit only if it blocks adoption. |
| **D2 macOS** | **Keep it, verified by CI.** No Mac and no hardware to test on by hand. | The suite runs on `macos-latest`, and the build job now runs the built binary's `--version`, `--help` and `config` on every OS. That is macOS's only gate, so it must stay green. |
| **D3 Python floor** | **Done: floor is 3.11** (`requires-python = ">=3.11"`, README says 3.11+), which is what CI tests. | Lowering it means adding that version to the CI matrix first. |
| **D4 Minimum Windows** | **Windows 8.1.** Verified with the installer on 6.3.9600 x64 against a real device. | Stated in the release notes. |
| **D5 Upgrade path** | **Won't test (psytrap).** The installer keeps the old AppId so it upgrades a po400 install, and `config.py` migrates the settings file. | Written and committed, deliberately not exercised on a machine with po400 installed. Both degrade safely: a failed migration just re-asks for the working directory. |

---

## 3c2. Windows test cadence (psytrap, 2026-10-15)

Two tiers, deliberately different cadence:

- **Every push (CI, mock only).** GitHub runners have no oximeter, so this was
  already the only thing CI *could* do -- stating it here makes it a decision,
  not an accident. **Closed (psytrap, 2026-10-15), implemented locally, not a
  handoff:** `tests/hwsim.py` gained `FakeHidDevice`/`make_fake_hid_module`, a
  fake `hid` module driving the real `HidBackend` through its full command
  sequence the same way `HidrawSim` drives `LinuxHidrawBackend` -- the fake
  needs no OS/kernel emulation at all (`HidBackend` only ever calls plain
  Python methods), so it is a fraction of `HidrawSim`'s size. `tests/
  test_hwsim_hidbackend.py` is platform-neutral (no Linux gate) and mirrors
  the real-trace flow tests: sessions, download, info, and the same T1/T3/T4/T6
  findings reproduce through this transport too -- confirming they are
  protocol-level bugs, not backend-specific ones. Primary coverage is the
  `hidapi`/`hid.device` shape (what CI and the shipped binary install); the
  `hid`/`hid.Device` shape gets a smoke test. Verified by sabotage: disabling
  the fake's own report-ID stripping breaks 7 of 13 tests, and reintroducing
  the exact pre-`0ab3bf0` enumerate-error bug flips the regression guard built
  for it -- both confirm the suite catches real defects, not just passes by
  construction. 251 tests total (was 238), runtime unchanged (~5-6s) once the
  same `VirtualClock` speedup the Linux flows use was wired in (13s -> 0.3s for
  this file alone). Does **not** and cannot prove the W1-W5 real-Windows-stack
  hypotheses in `handoff/ci-mock-hardware-response.md` -- those need the
  physical laptop regardless of how much mock coverage exists.
- **Real hardware (G5/G6), at release candidates only.** Not on every patch.
  Requires the physical Windows 8.1 laptop and is run by psytrap before tagging,
  same as Linux. CI cannot do this regardless of cadence -- there is no device
  on a GitHub runner -- so this is a statement of intent, not a workaround.

The W1-W5 Windows HID-stack hypotheses in `handoff/ci-mock-hardware-response.md`
are a third thing: one-time environmental questions, not per-release checks.
Settle each once on the laptop, record the answer here, and only revisit if
`HidBackend` changes substantially.

## 3d. Open findings (not release blockers until confirmed on hardware)

**Full investigation history moved to `CHANGELOG.md`** (2026-10-16) to keep
this file navigable -- T1-T8's discovery/fix narrative and the complete
Manual-mode protocol discovery story (how `0xA0`/`0xD0`, `0xA2`/`0xD2`,
`0xA3`/`0xD3`, `0xA7`/`0xD8` were found, every ruled-out hypothesis along
the way, and the delta-decode investigation) now live there. This section
keeps only current, live status.

**T1-T7:** fixed in patch 0013, verified on the real device (`sessions`/
`download` correct, `info` honest about unanswered fields). T1's
finger-out sentinel path (SpO2 127 / pulse 255) is still untested against
real hardware -- no real recording has hit a finger-out moment yet, and
there's an unconfirmed hypothesis that the device's own recording stops
rather than continuing with probe-out-flagged samples when the finger
comes off, which would make this path unreachable via the storage
protocol regardless of the decoder.

**T8 (open):** the Linux `hid` (libusb) backend's unlock handshake and RTC
read get no usable reply on this machine (`hidraw` is unaffected, and the
identical code works fine on the Windows laptop's `hid` backend). Likely
needs a genuine USB re-enumeration to clear, not more elapsed time --
untested, not remotely automatable. Low real-world severity: `hidraw` is
the real Linux path; Windows and (unconfirmed) macOS use their native HID
backends, not libusb. Repro: `fiedle400 selftest -b hid`. Full detail,
including the most recent re-confirmation: `CHANGELOG.md`.

**Serial-stream device support: deliberately deferred, not a gap
(psytrap, 2026-10-15).** This hardware unit only exercises the
flash/storage path (`0x9C`/`0x9D`); the serial-stream device family
`PROTOCOL.md` documents (where `0xA5`/`0xA6` apply) is untested because no
such device is available to test against, not because it was missed.
Support for it will be added in the future, when that becomes relevant --
not a current release blocker or open bug.

**Manual-mode protocol:** fully reverse-engineered and documented in
`PROTOCOL.md` §3.14/§3.15 and the German mirror in
`analysis/po400_bytemap_reference.md` -- not yet implemented in
`fiedle400` itself (cloud's side of the project's division of labor; the
protocol side is documented and ready). Two genuinely open questions
remain, both needing a physical recording on the device rather than more
analysis of the existing capture: (a) what record offset `0x04` actually
encodes (ruled out: a constant per-series channel ID, contradicted by live
data); (b) whether the header's duration field is the authoritative sample
count with everything past it being discardable padding, or something
else -- needs a precisely stopwatch-timed recording to settle. Full
discovery narrative and every ruled-out hypothesis: `CHANGELOG.md`.

> [!WARNING]
> **Process gap, v0.2.17 / 0.3.0 cycle (psytrap, 2026-10-15): G5/G6 were
> not actually satisfied before shipping, and a same-day retroactive check
> did not close it either.** The cycle was tagged and released on doc-only
> changes without re-running the real-hardware gates first. A same-day
> catch-up run (`info`/`sessions` against the real shipped binary, plus
> `FIEDLE400_LIVE=1` tests) only proved: Linux `hidraw` connect, handshake,
> RTC, and an *empty* session query all still work. It did **not** cover:
> (a) **Windows** -- no run on the laptop happened this cycle at all, and
> nothing here can substitute for one; (b) **real stored data** -- the
> device currently holds zero sessions (erased by this session's own
> Manual-mode testing), so `download` against an actual multi-record
> session -- the part T6/T7/the storage decoder exist to protect -- was not
> exercised, on either platform. G5/G6 for this cycle should be treated as
> **not done**, not as retroactively passed. Closing this needs: a real
> Manual *and* Auto-mode recording with actual data on the device, and a
> run of `fiedle400 selftest` (or the fuller G5/G6 commands above) on both
> Linux and the Windows laptop against that data -- not something that can
> be completed from here alone.
---

## 3e. TODO: recheck all tests for similar quirks (psytrap, 2026-10-15)

Prompted by the `selftest` CI incident (`98a9b08` -> `64e1c65` -> `770daf0`):
`command_selftest`'s Linux sysfs check called the real `find_pulsox_hid_devices()`
unconditionally, which passed locally (real device attached) and failed on CI
(no device) -- an environment assumption baked into a test, not caught until
CI ran on different hardware than the one it was written against.

Audit the rest of the suite for the same shape of mistake: any test that calls
through to something environment-dependent (the real filesystem, real device
enumeration, a real network call, wall-clock time) without mocking it, and
that happens to pass only because of what this development machine has
attached, installed, or happens to return right now. **Audit delivered in patch 0014** (findings and open proposals: `handoff/clean-audit-response.md`).

**TODO (psytrap, 2026-10-15): cross-check the test suite for code smell.**
Broader than the environment-assumption audit above -- a pass over
`tests/` for the usual smells (duplicated setup that should be a fixture,
assertions too weak to catch the regression they're named for, tests that
pass for the wrong reason, dead/unreachable test code, overfit mocks that
would still pass after the real implementation broke). Not yet done.

**TODO (psytrap, 2026-10-15): broader clean-code / clean-docs / clean-test /
clean-release audit.** A full pass across the project, not limited to
`tests/`:
- **Clean code:** dead code, unused imports/functions, duplicated logic that
  should be a shared helper, leftover debug prints, inconsistent naming.
- **Clean docs:** stale claims in `PROTOCOL.md`, `analysis/*.md`, `README.md`,
  `PACKAGING.md` that no longer match the current code (the opposite
  direction of the protocol-doc corrections already done this session --
  code/doc drift, not just protocol-vs-hardware drift).
- **Clean tests:** the code-smell item above, plus coverage gaps.
- **Clean release:** workflow files, `RELEASE_PLAN.md` itself for stale
  "today" status lines that no longer reflect reality, and repo settings
  (the kind of thing the `default_workflow_permissions` fix this session
  surfaced -- check for other drift between what's documented and what's
  actually configured).
Not yet done.

---

## 3f. Alpha vs. beta (psytrap, 2026-10-15)

**Alpha** ships without G7: all other gates (G1-G6) pass, but nobody has yet
recorded a real session with a finger on the probe and confirmed the plot
looks physiologically plausible. The tag/version stay plain semver
(`bump_version.py` only accepts `X.Y.Z`); alpha status is signalled by marking
the GitHub Release itself as a **pre-release**, not by a version suffix.

**Beta** means G7 is done -- real-world tests completed, not just the
simulator or a scripted hardware check. Promote by re-running the release
flow with `prerelease: false` once G7 passes; no version bump is required
just for that promotion.

---

## 4. Rollout Rings

### Ring 0: Local Release Candidate
1. Land B1–B7 as separate commits; G1–G4 pass locally.
2. **Phase 1:** `python3 scripts/bump_version.py patch` → `0.1.1`. Commit as `chore(release): v0.1.1`.
3. Diff audit (§1), then G5–G7 on the user's machine.
4. Tag: `git tag -a v0.1.1 -m "Release v0.1.1"`. The tag stays local until Ring 1.

### Ring 1: CI Build (dry run)
1. Run `build-release.yml` via **workflow_dispatch** on `master` (no tag, so the release job is skipped).
2. Download all three artifacts and smoke-test each on its own OS: `--version`, `--help`, `info` with the device attached (`info` now also prints the tool version and build). **This is the early-testing ring, the analogue of RefDiff's `common.js` harness.**

### Ring 2: Tagged GitHub Release
1. `git push origin v0.1.1`. The workflow builds and publishes the GitHub Release.
2. Release notes: what's new, udev rule, Windows `hid` note, checksums.

### Ring 3: Post-Shipment Verification & Feature Bump
1. **Live audit (the analogue of `check:deploy`):** download each published asset from the Release page, verify SHA-256 against the CI artifacts, and run `--version` to confirm it prints `0.1.1`.
2. **Phase 2 (final step):** only when Ring 3.1 passes and the user has reviewed the feature work: `python3 scripts/bump_version.py minor` → `0.2.0`, committed as `chore(release): open 0.2.0 after v0.1.1`. No tag; the next cycle's patch bump produces `0.2.1`.

---

## 5. Rollback

- **P0 (binary crashes, data corruption, `clear` erases unexpectedly):** mark the GitHub Release as pre-release or delete its assets; `git revert` the offending commit; ship a fix with a new patch RC (`0.1.2`). Never move or re-push an existing tag.
- **P1 (decode edge case, cosmetic):** fix forward in the next cycle. `download` is non-destructive, so users can re-download after updating.

---

## 6. Runbook Checklist

Per-cycle checklist -- re-check every box for each release, rather than
treating a past cycle's checked boxes as still valid. Versions below are
examples, not a record of what shipped; see `CHANGELOG.md` and git tags
for that.

- [ ] B1-B7 (or this cycle's blockers) landed as separate commits; G1-G4 green locally
- [ ] Phase 1: `bump_version.py patch`, run **once** per cycle
- [ ] Diff audit: `git diff --stat && git diff`, zero debris
- [ ] G5: built binary runs `info` / `sessions` on the real device, Linux *and* Windows, against a session with actual stored data (not an empty device -- see the v0.2.17 process-gap warning in §3d)
- [ ] G6: live device tests pass (Linux: `hidraw` and `hid`; Windows: `hid`)
- [ ] G7: real-finger session downloaded and plotted; user acknowledged the plot
- [ ] Ring 0: annotated tag created locally
- [ ] Ring 1: workflow_dispatch dry run; all 3 binaries smoke-tested on their OS
- [ ] Ring 2: push tag; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256 matches CI, `--version` matches the tag)
- [ ] Phase 2 (final step, after user review): `bump_version.py minor`
