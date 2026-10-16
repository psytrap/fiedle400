# fiedle400: Test & Release Plan

> **Scope:** First tagged release of the `fiedle400` CLI (GitHub Release with Linux, Windows and macOS binaries)
> **Cadence:** Two-Phase Version Bump (Patch Pre-Flight • Minor Post-Shipment), adapted from the RefDiff rollout plan
> **Baseline:** see `fiedle400/__init__.py` for the current version (patch-bumped freely per §1's rule; no git tags exist yet)
> **Status:** Strategy approved by psytrap (2026-10-15). All blockers B1–B7 resolved. The `fiedle400` rename (§3b, patch 0010) has landed. Findings T2-T7 (§3d) are **fixed in patch 0013 and verified against the real device** -- not just the simulator: `sessions`/`download` on the real PO-400 now correctly show 107 records / 1m 47s (was 214 / 4m 03s), and `info` honestly reports fields the device never answers instead of inventing them. **T1 is marked unfixed** (2026-10-16): its synthetic-only coverage doesn't count as a real-hardware fix; a loud runtime alert now covers its first real occurrence instead. A new finding, T8, was found afterward (Linux `hid`/libusb backend). `fiedle400 selftest` (new) gives a one-command, read-only hardware check with no env var needed. Nothing has been tagged or released.
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

All gates must pass on the patch-bumped RC before tagging. **Pre-flight is
not complete until the commit is pushed and G10 (GitHub CI) has actually
run on it (psytrap, 2026-10-16)** -- G1-G4 passing locally is necessary but
not sufficient; "pre-flight done" means the exact commit is on GitHub and
`tests.yml` has reported back, not just that local checks were green.

```bash
python3 scripts/bump_version.py patch                      # Phase 1: once per cycle
git diff --stat && git diff                                # Diff audit: zero debris
python3 -m unittest discover -s tests -t . -v             # G1/G2: full mock suite
python3 -m fiedle400 --version && python3 -m fiedle400 --help      # G4: stdlib-only smoke test (no matplotlib)
git commit && git push                                      # required before G10 can run at all
# G10: wait for tests.yml on this exact commit, then check its result
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
| **G5 Binary build** *(local only)* | `pyinstaller fiedle400.spec` succeeds, **and the built artifact runs a device-touching command** (`info`, then `sessions`) with a real PO-400 attached; for Windows, the installed binary from the installer. `--version`/`--help` alone are not enough: a binary that starts but cannot load the `hid` extension passes them (this happened before `0ab3bf0`). CI runners have no oximeter, so this gate can only run on psytrap's machines; CI only proves the build succeeds. | ✅ **Both platforms re-verified at `0.3.7` (psytrap, 2026-10-16).** Linux: PyInstaller in `.venv`, `info`/`sessions` correct against the real device (`hidraw`). Windows 8.1 laptop (reached over SSH): PyInstaller installed for `py -3.8`, built `dist\fiedle400.exe`, `info`/`sessions` both correct against the same real device (`hid` backend; clock honestly "not reported by the device" there too). Not yet done via the installer/`.iss`, only the raw PyInstaller build -- fine for this gate's purpose. **Linux re-verified again at `0.3.8` (psytrap, 2026-10-16)** after the wizard/udev/desktop-launcher patch: rebuilt (43MB, matplotlib now actually bundled -- the earlier `0.3.7`-era Linux builds this session were accidentally built from a `.venv` without matplotlib installed, so `plot` silently degraded; fixed), `info`/`sessions` correct against the real device. **Windows re-verified too at `0.3.8` (psytrap, 2026-10-16):** repo re-synced to the laptop (it was stale), rebuilt with `py -3.8`, `dist\fiedle400.exe info` correct against the real device (`hid` backend, clock honestly "not reported by the device"). |
| **G6 Live hardware** *(mandatory, the analogue of RefDiff's live CDP invariant)* | `FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live` passes with a real PO-400 attached, on Linux with **both** backends (`hidraw` and `hid`); elsewhere with `hid` only (`hidraw` raises off Linux by design, and the Linux-only tests skip with a reason). Never run two live runs at once (a lock file serialises them). `fiedle400 selftest` runs the same core checks with no env var, for a quick one-off. | ✅ **Both platforms re-verified at `0.3.7` (psytrap, 2026-10-16).** Linux `hidraw`: `fiedle400 selftest` all 5 checks pass, clock query returns the exact bytes the patch predicted (`f2 00 00 02 07 00 0c 07`); `FIEDLE400_LIVE=1` suite 7/7 pass. `hid` backend on Linux still reproduces T8 exactly as documented -- unchanged, not a regression, expected per T8's "won't fix" call. Windows 8.1 laptop: `FIEDLE400_LIVE=1 py -3.8 -m unittest tests.test_device_live -v` -- 5/5 applicable tests pass (`hid` backend enumeration, connection, handshake, clock, sessions), 2 correctly skipped as Linux-only. **Linux re-verified again at `0.3.8`:** `FIEDLE400_LIVE=1` suite 7/7 pass. **Windows re-verified too at `0.3.8`:** `FIEDLE400_LIVE=1 py -3.8 -m unittest tests.test_device_live -v` -- 5/5 applicable pass, 2 correctly skipped as Linux-only. |
| **G7 Visual & data acknowledgment** | Record a short session **with a finger on the probe**, download it to `.spo2`, `.csv` and `.json`, run `fiedle400 plot`, and have the user confirm the PNG looks physiologically plausible. Per `.agents/rules/implausible_data_warning.md`, constant 95/64 or 99/95 values with probe-out flags fail this gate. | ✅ **Re-verified at `0.3.7` (psytrap, 2026-10-16).** Real stored session (160 records / 2m40s) downloaded from the device and plotted: SpO2 94-99% (avg 96.9), HR 63-86 bpm (avg 73.7), real variation, 0 dropouts, no probe-out pattern. `info` correctly reports the clock as "not reported by the device" against the live device, matching the patch's claim end-to-end. Prior pass: 2026-10-15 (92/937-record sessions, SpO2 92-99%, HR 49-81). |
| **G8 Output location** | Per `AGENTS.md`, output goes to the current directory (or the configured workdir), never a hard-coded `output/`; help strings say the same. | ✅ The code always wrote to the cwd; only the help strings said `output/`. Fixed in `9647913`. |
| **G10 GitHub CI** *(pre-flight, psytrap, 2026-10-16)* | `tests.yml` (ubuntu/windows/macos, Python 3.11) should be green **on the exact commit being tagged**, not just "green at some point" -- a local-only pass of G1-G4 only proves one OS/Python combination. **Non-blocking:** check it and record the result, but a CI run that's red doesn't by itself stop a release the way G1-G7 failing would -- CI can be environmentally flaky in ways the local hardware gates aren't. If it's red, look at why before deciding whether to fix forward or tag anyway. | ✅ Commit `d797819`: [run 38866641138](https://github.com/psytrap/fiedle400/actions/runs/38866641138) green on all three OSes. |

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

**T2-T7:** fixed in patch 0013, verified on the real device (`sessions`/
`download` correct, `info` honest about unanswered fields).

**T1: marked unfixed (psytrap, 2026-10-16), downgraded from "fixed in
patch 0013."** The sentinel decode (SpO2 127 / pulse 255 -> `probe-out`)
is implemented and passes synthetic tests, but has **never once fired
against real hardware** -- no real recording has hit a finger-out moment
yet. Code that has only ever been exercised by hand-built test frames
does not count as fixed here, regardless of how confident the synthetic
coverage looks. There's also an unconfirmed hypothesis that the device's
own recording stops rather than continuing with probe-out-flagged samples
when the finger comes off, which would make this path structurally
unreachable via the storage protocol regardless of the decoder -- in
which case "fixed" may not even be a meaningful status for it.
**Mitigation added (2026-10-16):** `fiedle400 download` now scans every
downloaded record for the literal `probe-out` sentinel flag and, if it
ever fires for the first time on real data, prints a loud alert
(`fiedle400/cli.py:_probe_out_alert`) asking whoever sees it to file a bug
report with the capture attached. Covered by
`tests/test_cli_graceful.py::TestProbeOutAlert`. This doesn't fix T1 --
it just guarantees the first real occurrence can't pass unnoticed.
**Won't fix in the next release (psytrap, 2026-10-16):** ships with the
alert-only mitigation above; not a blocker.

**T8 (open):** the Linux `hid` (libusb) backend's unlock handshake and RTC
read get no usable reply on this machine (`hidraw` is unaffected, and the
identical code works fine on the Windows laptop's `hid` backend). Likely
needs a genuine USB re-enumeration to clear, not more elapsed time --
untested, not remotely automatable. Low real-world severity: `hidraw` is
the real Linux path; Windows and (unconfirmed) macOS use their native HID
backends, not libusb. Repro: `fiedle400 selftest -b hid` (since 0.3.7; `fiedle400 -b hid selftest` works in every version). Full detail,
including the most recent re-confirmation: `CHANGELOG.md`.
**Won't fix in the next release (psytrap, 2026-10-16):** `hidraw` remains
the supported Linux backend; not a blocker.
**New evidence, same day:** `fiedle400 selftest`'s new automatic
both-backend probe (added this session) has shown `hid` both reproducing
T8 (bare ACK, no data) *and*, after the device was unplugged and
reconnected a few times in between, passing cleanly -- all 5 checks,
matching `hidraw` exactly. Consistent with, not yet confirmation of, the
"needs a genuine USB re-enumeration" theory; still not reliably
reproducible on demand, so still open, still not a blocker.

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

(The v0.2.17 / 0.3.0 process-gap warning is in §2, below the gate table.)
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
would still pass after the real implementation broke). **Delivered with the clean audit in patch 0014** (`handoff/clean-audit-response.md`).

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
**Delivered in patch 0014** (`handoff/clean-audit-response.md`); the `PROTOCOL.md` /
`analysis/*.md` pass followed separately (`handoff/docs-review-response.md`).

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

## 3g. New TODOs (psytrap, 2026-10-16)

- **Test the udev installer against an existing/stale config.** ✅ **Done
  (psytrap, 2026-10-16).** Tested via a simulated `RULES_DIR` (no real root
  or system files touched): refuses without root, is idempotent on an
  unchanged rule, and correctly detected a differing rule (wrong
  `MODE`/`GROUP`, simulating a stale install). Per psytrap, silently
  overwriting was wrong -- `write_rule()` now shows the existing vs. new
  content and asks `Overwrite? [y/N]` before touching a file that already
  exists with different content; declining leaves it untouched and warns the
  device may not work until it's resolved. A same-content file is still
  skipped silently ("Already up to date") since there's nothing to decide.
  (A differently-*named* leftover file, e.g. an old `99-po400.rules`, is
  simply not touched either way -- it was never going to conflict since
  udev applies all matching rules, just noise to clean up by hand.)
- **Manual-mode real-hardware recording: optional release gate.** Add a new
  gate (call it **G9**) that is explicitly *not* a blocker: before tagging,
  ask whoever is running the release whether they can supply one real
  Manual-mode recording (a capture or a `.spo2`/trace from the device in
  Manual mode). If provided, use it to settle the open Manual-mode questions
  in `PROTOCOL.md` §3.14 (M1-M7, `handoff/docs-review-response.md`). If not
  provided, note it as skipped and ship anyway -- Manual mode isn't
  implemented in `fiedle400` yet, so this never blocks a release, it only
  improves the docs when the data happens to be available. Not yet done.
- **Linux desktop icon.** ✅ **Done (psytrap, 2026-10-16).** No custom icon
  artwork exists anywhere in the project for *either* platform (the Windows
  shortcut just uses PyInstaller's default EXE icon), so this is a
  generic-icon terminal launcher, not matching artwork -- a real icon is a
  separate, future task. `install.sh` now writes
  `~/.local/share/applications/fiedle400.desktop` (`Icon=utilities-system-monitor`,
  a stock icon that reads as a pulse/activity graph -- per psytrap's request
  for "something that looks like a measurement"; `Terminal=true` since this
  is a console app). Per psytrap's question about the working directory:
  the Desktop Entry spec's `Path=` key takes a literal path, no `$HOME`
  expansion at launch time, so `install.sh` resolves and creates
  `~/Documents/fiedle400` at install time and bakes that in -- mirrors the
  Windows installer's `WorkingDir: {userdocs}\PO-400` pattern, so recordings
  land in one predictable folder instead of the home directory root.
  Verified: installed for real, `desktop-file-validate` passes clean,
  `--uninstall` removes it too.
- **State plainly that "not reported by the device" may be a device bug, not
  just an unimplemented feature.** ✅ **Done (psytrap, 2026-10-16).** Added
  to `PROTOCOL.md` §3.3 (the full argument: vendor's own software has the
  identical gap, and the reply never varies across recordings a month apart
  through a clock-set in between) and a shorter pointer in `README.md` next
  to the clock feature bullet.
- **Interactive wizard: "download all" should ask for output format first.**
  Today (`run_interactive_wizard`, `fiedle400/cli.py` ~line 790), after
  picking sessions (including `[A]`/`[W]` "all") the wizard goes straight to
  a "Save as [default: ...]" filename prompt; format is only chosen as a
  side effect of typing `1`/`spo2`, `2`/`csv` or `3`/`json` *into* that same
  prompt instead of a plain filename. Confirmed transcript (psytrap,
  2026-10-16):
  ```
  Select action [W, 1-2, ranges, a, c, q; default: W]: w
  Start Download Wizard to download all sessions? [Y/n]:
  Save as [default: fiedle400_2026-10-16T083731_2026-10-16T084342.spo2]:
  ```
  Add a separate "Output format: [1] spo2 (default) [2] csv [3] json"
  prompt **before** this "Save as" step (default: spo2, i.e. today's
  behaviour unchanged if the user just presses Enter at both prompts), so
  format and filename become two distinct, clearly labelled questions
  instead of one prompt doing both jobs. ✅ **Done (psytrap, 2026-10-16),**
  `fiedle400/cli.py` `run_interactive_wizard`; also made the action-selection
  prompt itself more visible (`>>> Select action [...]`, on its own line
  below the menu box) per psytrap's request. `tests/test_cli_interactive.py`
  updated for the extra prompt; 259 tests pass.
- **TODO: check for better options than mocking `builtins.input` in the
  Windows CI job.** `tests/test_cli_interactive.py` drives the interactive
  wizard by patching `builtins.input` with a canned `side_effect` list --
  confirmed (psytrap, 2026-10-16) this is pure Python mocking with no real
  stdin/console involved, so it behaves identically on all three `tests.yml`
  runners (`ubuntu-latest`, `windows-latest`, `macos-latest`) and isn't
  actually testing anything Windows-console-specific about the wizard's
  interactive behaviour. Worth a look at whether a more realistic approach
  (a real pty / real subprocess with piped stdin) would catch bugs the
  mock can't -- e.g. console encoding quirks, Windows-specific `readline`
  behaviour. Not yet done; no known bug motivating it today, just a gap in
  how faithfully the test doubles for a real terminal.
- **TODO (psytrap, 2026-10-16): wizard's `png` path should offer to open the
  image.** After `run_interactive_wizard` renders the plot (`fiedle400/cli.py`,
  the `want_plot` block), ask "Open the plot now? [Y/n]" (default yes) and,
  if accepted, open it in the system's default image viewer -- `xdg-open` on
  Linux, `os.startfile` on Windows, `open` on macOS (each already a stdlib/
  OS-provided mechanism, no new dependency). Not yet done.

---

## 4. Rollout Rings

### Ring 0: Local Release Candidate
1. Land B1–B7 as separate commits; G1–G4 pass locally.
2. **Phase 1:** `python3 scripts/bump_version.py patch` → `0.1.1`. Commit as `chore(release): v0.1.1`.
3. Diff audit (§1), then G5–G7 on the user's machine.
4. **G10** (pre-flight, non-blocking): once the commit is pushed, check `tests.yml` went green on it.
5. Tag: `git tag -a v0.1.1 -m "Release v0.1.1"`. The tag stays local until Ring 1.

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
- [ ] **Pre-flight is not "done" until this commit is pushed and G10 has actually run and reported back** -- not optional, not just G1-G4 locally (psytrap, 2026-10-16)
- [ ] G5: built binary runs `info` / `sessions` on the real device, Linux *and* Windows, against a session with actual stored data (not an empty device -- see the v0.2.17 process-gap warning in §3d)
- [ ] G6: live device tests pass (Linux: `hidraw` and `hid`; Windows: `hid`)
- [ ] G7: real-finger session downloaded and plotted; user acknowledged the plot
- [ ] G10 (non-blocking **for tagging**, but required for pre-flight to count as complete): `tests.yml` checked on that exact commit (ubuntu/windows/macos)
- [ ] Ring 0: annotated tag created locally
- [ ] Ring 1: workflow_dispatch dry run; all 3 binaries smoke-tested on their OS
- [ ] Ring 2: push tag; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256 matches CI, `--version` matches the tag)
- [ ] Phase 2 (final step, after user review): `bump_version.py minor`
