# fiedle400: Test & Release Plan

> **Scope:** First tagged release of the `fiedle400` CLI (GitHub Release with Linux, Windows and macOS binaries)
> **Cadence:** Two-Phase Version Bump (Patch Pre-Flight • Minor Post-Shipment), adapted from the RefDiff rollout plan
> **Baseline:** `0.1.12` (patch-bumped freely per §1's rule; `master` has 51 commits; no git tags exist yet)
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
| **D3 Python floor** | **Open.** `requires-python = ">=3.8"` while CI tests only 3.11. | Either add 3.8 to the matrix or raise the floor to what is actually tested. |
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

## 3d. TODO: open findings (not release blockers until confirmed on hardware)

Found while building the simulated-hardware tests (`tests/hwsim.py`, `tests/test_hwsim_linux.py`, `tests/test_hwsim_realtrace.py`). Each is pinned by an `expectedFailure` test that starts passing, and is reported as an unexpected success, when the defect is fixed. T1-T5 were first reproduced against the vendor-tool capture `analysis/bum400_20260906_100516.pcap`; `tests/fixtures/cli-exchange.trace.json` is the CLI's own traffic with the real device (Windows 8.1, hid backend, 214-sample session, recorded 2026-10-15) and confirms or extends them as noted per row. T6 and T7 come from that recording.

**DONE (psytrap, 2026-10-15):** a real ~15.5 minute session (937 records,
session 3, recorded same day) settled this. `fiedle400 download` gave
937/937 records, 0 sequence gaps, matching the header exactly; the exported
CSV has 0 duplicate timestamps and a uniform 1.00s gap end to end across the
whole span -- no T6-style overlap or repetition anywhere, crossing roughly
4-5 window-boundary transitions (937 raw samples over a ~214-per-window
capacity). T6's fix holds on real multi-window data, not just the simulator.
Plotted and sent to psytrap for the G7 visual check alongside a second,
shorter real session (92 records) recorded the same day.

Still not settled by either recording: neither contains a finger-out moment
(both report `flags=ok` throughout), so T1's sentinel path (SpO2 127 / pulse
255) remains untested against real hardware -- synthetic frames only.

**Serial-stream device support: deliberately deferred, not a gap
(psytrap, 2026-10-15).** This hardware unit only exercises the
flash/storage path (`0x9C`/`0x9D`); the serial-stream device family
`PROTOCOL.md` documents (where `0xA5`/`0xA6` apply) is untested because no
such device is available to test against, not because it was missed.
Support for it will be added in the future, when that becomes relevant --
not a current release blocker or open bug.

**Update (psytrap, 2026-10-15), unconfirmed:** deliberately pulled the probe
off mid-recording to test this. psytrap's hypothesis: the device's own
recording stops (rather than continuing and writing probe-out-flagged
samples) when the finger comes off. Not yet verified technically -- if true,
T1's sentinel path may be effectively unreachable via the storage path on
this firmware regardless of the decoder fix.

**Separate observation, corrected (psytrap, 2026-10-15):** `sessions` went
from 3 visible, to 1, to 0, over the course of this testing. The first
hypothesis here was that this was only a query/indexing mismatch -- Auto vs
Manual recording mode -- with the data still intact on the device. **Status
uncertain, not contradicted:** after an explicit Record on-then-off cycle,
the device's own display shows **no session-count indicator at all** --
not an explicit "0". Ambiguous: this could mean zero sessions (some UIs
only show a count when there is something to count), or that psytrap was
not on the screen that would show one. Not yet resolved either way.

**Mechanism for sessions 1-3's disappearance, confirmed (psytrap):** switching
the device from Auto to Manual recording mode erases its memory. That fully
explains the 3 -> 1 -> 0 sequence; not a protocol or query bug.

**User-slot hypothesis, tested and ruled out:** `PROTOCOL.md` 3.13 documents
per-user erase for slots 1-6 (`0x91`..`0x96`), while the implemented
`QUERY_SESSIONS`/`SESSION_RESET` commands (`commands.py`
`build_session_index_query_command`/`build_reset_session_index_command`) take
no user parameter at all -- hardcoded to slot 1. Tested directly on hardware
whether byte `[1]` doubles as a user selector there too, mirroring the erase
command's framing: queried slots 1 through 6 explicitly after a fresh Manual-
mode recording. **All six returned the identical bare `COMMAND_ACK`, not
`0xEC` data for any slot.** This rules out "stored under a different user
slot, unreachable by our hardcoded query" -- if that were true, at least one
slot should have answered with real data. The simpler explanation now looks
more likely: the Manual on-then-off cycle did not actually commit an indexed
session at all, for a reason not yet found (missing a save/confirm step on
the device? a minimum-duration threshold?) -- not a protocol addressing gap
in this tool. Still needs confirming directly on the device's own UI.

**Independent confirmation found in the vendor's own software (psytrap, found
via static analysis of `archive/bruteforce/SpO2.exe`, not git-tracked --
`.gitignore`d, a pre-existing local artifact from the original protocol
reverse-engineering, same method `PROTOCOL.md`'s own header credits):** its
UTF-16LE strings include the literal confirmation-dialog text *"Changing the
storage mode will erase the stored data in the device. Are you sure you want
to do this?"*, plus internal names `STR_StorageAuto`, `STR_StorageManual`,
`STR_ChangeStorageModelNote`, `bAutoDeleteSegmentSaveData`,
`bManualDeleteSegmentSaveData`. "Storage Model" (Auto/Manual) is a real,
named, vendor-acknowledged concept with its own erase warning -- independent
confirmation of the mode-switch-erase finding above, not a misreading on our
side.

**`SESSION_SELECT`/`SESSION_DOWNLOAD` (`0xA5`/`0xA6`) hypothesis, tested and
ruled out on real hardware:** `PROTOCOL.md` 3.12 already flags these as "used
on serial-stream device models" (this one is flash/storage-based, via
`0x9C`/`0x9D`), raising the question of whether Manual-mode sessions route
through that other addressing scheme instead. Tested directly: unlock,
flush, `reset_session_index`, flush, then `SESSION_SELECT`+`SESSION_DOWNLOAD`
for session IDs 1-3, each read immediately after. All six writes got **no
reply at all** -- not even a bare ACK. Sanity-checked on the same connection
immediately after: a raw `READ_RTC` (`0x82`) built the identical way got a
correct, well-formed reply, confirming the test method itself was sound. This
firmware does not answer `0xA5`/`0xA6`; ruled out, not a dead end from a
bug in the test.

A heuristic static scan of the vendor exe for undocumented command templates
(byte sequences matching this project's own `sum(bytes) % 128` checksum
convention) was tried and abandoned: a 3.3MB binary has enough coincidental
matches that it did not discriminate real command tables from random data
without much tighter constraints than attempted. Not pursued further -- the
remaining open question (how, or whether, a Manual-mode session can be read
via USB at all) is better answered by the device's own UI than more blind
byte-pattern guessing against an unfamiliar binary.

**RESOLVED (psytrap, 2026-10-15): Manual mode has its own, completely
separate protocol** -- `0xA0`/`0xD0` (header), `0xA2`/`0xD2` (pulse),
`0xA3`/`0xD3` (SpO2), `0xA7`/`0xD8` (block ack), found via a live USB capture
of SpO2 Assistant reading a real Manual recording, cross-referenced against
`SpO2.exe`'s disassembly. Full byte maps now in `PROTOCOL.md` §3.14 and
`analysis/po400_bytemap_reference.md`. This is why `0x9C`/`0x9D` (and the
ruled-out `0xA5`/`0xA6` hypothesis just above) never found anything: Manual
sessions were never reachable through the Auto-mode storage path at all, by
design, not by a bug. All the guessing above -- user slots, `0xA5`/`0xA6`,
the static byte-pattern scan -- correctly found nothing, because none of
those were the real mechanism.

Verified live against the real device, not just transcribed:
- `0xA0` header query: confirmed, but the original transcription had the
  date/time/duration fields one byte too early (missing an unidentified
  `0x00` byte at offset `0x01`); fixed in both docs.
- `0xA3`/`0xD3` and `0xA2`/`0xD2` data blocks: **framing confirmed, value
  decode formula not yet correct.** 3 reports, 7 subframes each, every
  subframe's checksum validates, and whole-`0x7F` sentinel subframes line up
  at the same positions in both streams (seq 0, 2, 5) -- strong evidence the
  two series are measured together, second by second. But decoding the
  non-sentinel bytes with the documented fixed-base-per-subframe formula
  gives overlapping, physiologically impossible values for both series
  (negative numbers, values over 127). Likely needs a running baseline
  (analogous to the storage path's own dynamic-baseline escape, §3.5.3)
  rather than one fixed value per subframe -- not yet tested.
- Device behaviour, independently clarified: Manual mode holds exactly **one**
  recording slot, overwritten every time a new Manual recording starts
  (psytrap, confirmed via the device's own on-screen warning). This explains
  both the mode-switch erasure (Auto and Manual use entirely separate storage)
  and why the queried duration (41 s) need not match any particular earlier
  recording attempt -- it reflects whatever is in that one slot right now.

Not yet done: the running-baseline hypothesis, and any actual code
implementation (`fiedle400` has zero support for these opcodes yet -- this is
new protocol knowledge, not a working decoder). Also unexplained: why SpO2
Assistant itself did not detect the device during this session (Windows-level
connect sound heard, device not shown in the app) despite having worked
before -- not reproduced further once the Manual-mode protocol investigation
took priority; the USBPcap/Wireshark capture tooling installed for this
(`enable_testsigning`, TESTSIGNING now on) remains unused for that specific
question and sits on the laptop for whenever it is revisited.

**RESOLVED: the Manual-mode delta decode is solved and verified (psytrap,
2026-10-15).** The base value sits at record offset `0x05`, not `0x03`. Two
earlier attempts read it from `0x03`, which inflated SpO2 to 116-127 and
produced negative Pulse values; that single off-by-two is what generated
both the bogus "subtract a constant 27-28" hypothesis and the bogus
"ramp-up transient" reading of subframes 1 and 3. Neither was real. With the
base at `0x05`, a running chain `S_n = S_(n-1) +/- magnitude` over
high-nibble-first sign/magnitude deltas from `0x06`, a shared `0x7F`
sentinel, byte-level `0x7F` padding and a nibble-level `0xF` end marker, all
8 data subframes decode to textbook values with no correction of any kind:
SpO2 96-100%, Pulse 62-67 bpm, 59 samples with signal over a ~140-sample
timeline, three no-finger gaps. Full spec and reference implementation in
PROTOCOL.md §3.14.F; German mirror in `analysis/po400_bytemap_reference.md`.
Notably the relayed disassembly note ("byte `0x04` of the data region is the
base") was **correct all along** -- counting the data region from the `seq`
byte, index 4 is `rec[5]`. The error was local, not in the relayed findings.

**Static disassembly of the local `SpO2.exe` is a confirmed dead end -- stop
trying.** Three methodologically independent scans agree this build does not
contain the Manual-mode decoder: alignment-independent raw byte-pattern
cluster search (shift-by-4 near a `0x0F`/`0x07` mask near a sign test, zero
hits), signed 4-bit lookup-table search across `.text`/`.rdata`/`.data`
(zero hits), and inspection of all 22 `[reg+5]`/`[reg+6]` load pairs (the
only promising one is DES in a crypto library at `0x42e2xx`). psytrap
confirmed the relayed disassembly came from a third installation, different
from both this archived copy and the laptop's V3.0.5. An earlier linear
capstone sweep that "found" clusters was desynced and its results are
void -- it reported 5 `and reg,7` in 1.7 MB where a raw scan finds 29. The
method notes, section table, useful byte encodings and known decoys are now
written up in PROTOCOL.md §3.15 so this is not re-attempted from scratch.
**RESOLVED: opcode `0xA4` is not a Manual-mode mystery -- it's an existing
Auto-mode opcode (live-checked against source, 2026-10-15).**
`fiedle400/protocol/models.py` already defines `0xA5` ("select active
session index slot") and `0xA6` ("initiate session download handshake") in
the same family as `0xA2` (`STORAGE_NEGOTIATION`), all part of the
already-implemented Auto-mode storage protocol. The disassembly whitelist
cluster that grouped `0xA2/0xA3/0xA4/0xA5/0xA6` together is that same
Auto-mode session-selection family, not a Manual-only opcode. A second
relayed disassembly pass (2026-10-15) gives it a specific role, not yet
re-verified against this project's own binary: `SEGMENT_QUERY` /
`SEGMENT_PREPARE`, sent once per stored segment in a loop
(`for i in 0..TotalSegments-1`) immediately before `0xA5`
(`SESSION_SELECT`) -- i.e. it walks the device's segment list to position
the read pointer before a specific session is selected. Plausible and
consistent with the A2/A5/A6 family it was already placed in; not pinned
down by direct testing here.

**Partially resolved: the duration-field discrepancy is real and
reproducible, not a one-off.** Re-pulled the exact same stored recording
live from the device (2026-10-15): byte-identical to the earlier capture,
confirming it is deterministic, not a transcription artifact. Header still
says 41 s. Subframe `seq=3` alone decodes to 27 samples with **no
terminator at all** -- it simply runs out of its 13 delta bytes without
ever hitting a `0x7F` byte or `0xF` nibble -- and the four non-"no-finger"
subframes total 59 real samples by themselves, already past 41. If each of
the 7 subframes instead represents a fixed ~5.86 s reporting window
(41 / 7) regardless of how many internal delta-samples it carries, the
totals reconcile, implying the device samples faster than 1 Hz internally
and the per-nibble index is not directly seconds. A second relayed
disassembly pass (2026-10-15) offers a specific mechanism for this: the
device's own reader (claimed at `0x00479fc5`, unverified build) allegedly
stops consuming samples once a running count reaches the header's duration
value, treating everything past that point -- even same-value deltas
indistinguishable from genuine flat readings -- as discardable block
padding. Credible, not independently checkable from raw bytes (that is
exactly the `0x00`-delta-vs-padding ambiguity already on this list).
Resolving it for real still needs a **precisely timed** fresh Manual
recording (e.g. exactly 20 s by stopwatch, started and stopped on the
device itself) compared against the resulting header duration and
decoded sample count -- a physical button-press on the device, not
something done from here.

**RESOLVED (two independent methods agree): high-nibble-first.** The
empirical smoothness check on this capture was a near-exact tie (23 vs 24
out of 189 points) and could not settle it alone. A second, independently
relayed disassembly description of the decode loop matches this project's
nibble math exactly (sign at bit 7 of the byte, magnitude in bits 6-4 for
the first sample; sign at bit 3, magnitude in bits 2-0 for the second) --
corroboration, not the origin, of what PROTOCOL.md §3.14.F already
specifies. Treat as settled unless a sharp-transition capture disagrees.

**Found and flagged, not resolved: the relayed claim about offsets
`0x03/0x04` does not match the live data.** The same disassembly pass
claimed `rec[0x04]` in this document's indexing (its own indexing counts
from the `seq` byte) is a constant hardware channel-ID byte, `0x08` for
SpO2 and `0x04` for Pulse. Checked directly against the live capture: it
is not constant -- `0x7C, 0x00, 0x7F, 0x7F` across SpO2's four real
subframes, `0x7D, 0x00, 0x7F, 0x7F` across Pulse's. Still unidentified;
specifically not a fixed per-series tag as claimed. A relayed claim that
contradicts a direct live measurement loses to the measurement.

**Also found and worth fixing in PROTOCOL.md's prose (not yet done):**
`build_hid_command` in `fiedle400/protocol/commands.py` pads unused report
bytes with `0x80`, not `0x00` -- a raw test write using `0x00` padding got
no response from the real device at all. And `UNLOCK_HANDSHAKE` + the
`0xA2` negotiation half are sent as **one** concatenated 64-byte write
(`build_unlock_negotiate_handshake`), not two separate 64-byte writes --
§3.1's two-table layout reads as if they are separate transmissions. Live
reproduced: the correct combined/padded framing works immediately; the
naive two-writes/0x00-padding framing gets silence.

Implementing the decoder in `fiedle400` is cloud's side of the split -- the
protocol side is documented and ready.


Raw trace of the session query after that cycle: a bare `COMMAND_ACK`
(`f0 70`), no `0xEC` data -- the same shape as T7's bare-ACK pattern on other
queries, now also seen on the session-index query itself. psytrap: "storage
concept must be different" -- i.e. our model of how this firmware creates
and retains a session (PROTOCOL.md's `MAX_SESSION_SLOTS` picture) may not
match how sessions 1-3 actually got created. Next step: establish exactly
what sequence produced sessions 1-3 in the first place, and try to reproduce
it -- guessing at menu modes without that is not converging. Still blocks:
T1's real finger-out test, and the Auto/Manual question itself (open again,
not resolved either way).

**Status: T1 to T7 are fixed in patch 0013 (the tests that pinned them now assert the correct behaviour) and verified on the real device (Windows 8.1 laptop, `0.1.11`), not just the simulator: `sessions`/`download` show 107/107 records in 1m 47s with 0 sequence gaps (was 214 padded records, 4m 03s), `info` shows `Device Model Descriptor: 50F` and honest "not reported by the device" for the rest, exactly as predicted before the run. The Next step column keeps the original proposals; each row ends with what was done. T8 (new, below) was found during that same verification pass -- the fix itself is confirmed correct; T8 is a separate, pre-existing backend quirk it happened to surface.**

| # | Finding | Evidence | Next step |
|:--|:---|:---|:---|
| **T1 Status flags read from the MSB mask byte** | `engine/detector.py` takes `flags = chunk[7]` of every 30-byte `0xED` frame, but PROTOCOL.md 3.5 defines byte 7 as the third MSB mask (`m2`), not a status field. Whenever a data byte in positions 22..28 has bit 7 set (every `0xF_` baseline escape does), `m2` is non-zero and the frame is reported as `searching`/`low-perfusion`. `engine/device.py` then stores those samples as `None`. | In the capture the last frame of each page (seq 5, `m2` = `0x60`) decodes as `searching,low-perfusion`; a download keeps 103 of 122 records and blanks the last 19. The other frames decode as `ok`. | **Confirmed on the real device** (`test_the_last_frame_of_a_window_is_read_as_probe_out_today`, `test_no_samples_are_lost_at_the_end_of_a_window`): each reply ends with a short filler frame (seq 5, 8 raw values) whose mask bytes are `0x7f`; byte 7 = `0x7f` reads as `probe-out,searching,low-perfusion`, so its 4 averaged pairs are not decoded (103 of 107 per reply, no `None` samples because the frame is skipped, not blanked). The CLI's "103/214 records" at the halfway checkpoint is this plus T6. **Unblocked (psytrap, 2026-10-15): proceed, flagged for double-checking rather than gated.** Byte 7 is `m2` (§3.5), not a status field, and the storage stream's own documented finger-out signal is different: a sentinel in the decoded value itself (`analysis/bum400_20260906_100516.md` §4 -- SpO2 out of range -> `0x7F`/127, pulse out of range -> `0xFF`/255), not a flag byte. Stop deriving probe-out from byte 7 for `0xED` frames; use the documented sentinel values instead. Re-verify against the 5-10 minute recording (TODO above) once it exists, and against the real serial-stream devices if any are available -- this device only exercises the storage path. **FIXED in patch 0013:** Both frames and flags: `engine/detector.py` no longer takes status flags from byte 7 of `0xED` series frames; a reply's short final frame (ends with the `0xFF 0xFF` terminator) is decoded like any other; out-of-range values (SpO2 127, pulse 255) mark the second as a finger-out record (`flags` = `probe-out`, SpO2 and pulse empty). Legacy single-sample frames keep their flag handling. **Flagged for double-checking (psytrap):** re-verify against the 5-10 minute recording and a real serial-stream device. |
| **T2 Silent device counts as a successful download** | With every reply dropped, `download` prints "No active session table returned; defaulting to downloading Session #1", saves an empty file and exits 0. | `test_device_that_never_answers_is_not_reported_as_a_successful_download` | Exit non-zero (and write no file) when no session answered or zero records came back. **FIXED in patch 0013:** `download` prints "No recording data was received from the device, so nothing was saved" and exits 1 without writing a file. |
| **T3** ✅ **confirmed** -- Session length is shown about twice too long | The header count (243) is raw 2 Hz values (`analysis/bum400_20260906_100516.md` section 5: 243 values = 122 s) and an independent decompression gives 243 values per series. `SessionInfo` treats it as seconds, so `sessions` shows 4m 03s for a 122 s recording and the engine never reaches its record target (it asks for page 1 and retries). PROTOCOL.md 3.2 and 1 also said "seconds" -- that mislabel is now fixed. **Mechanism confirmed by psytrap (2026-10-15):** the device genuinely takes two independent raw half-second readings per second -- not duplicates -- and the firmware/decoder average them into one physiological 1 Hz value. That is why the raw header count is exactly double the real duration: it counts the two half-second readings separately, before they are merged. Not a decode bug, a label bug -- the merge-by-averaging the decoder already does (`detector.py`: `round((v1+v2)/2.0)`) is correct and matches `analysis/bum400_20260906_100516.md` section 5's own description of the firmware behaviour. | `test_header_count_is_in_raw_2hz_samples_so_duration_is_about_two_minutes` (pcap, 243 -> 122 s), `test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds` (real, 214 -> 107 s) | Treat the header value as 2 Hz samples (duration = count // 2) in `SessionInfo`/the engine's record-count target. PROTOCOL.md §1 and §3.2 are fixed; §3.5.3 now states the confirmed merge mechanism. No decoder change needed -- the averaging was already correct, only the field's label and the duration/count math around it were wrong. **FIXED in patch 0013:** `parse_session_index_table` reads the 0xEC count as raw samples: `SessionInfo.raw_samples` = count, `record_count` = `duration_sec` = `(count + 1) // 2` (an odd count keeps its last reading: 243 -> 122, matching the 122 records decoded from the capture). Decoder unchanged. |
| **T4 `info` prints made-up values** | When the device does not answer, `command_info` still prints firmware "v2.0", serial "50F", user "user" and geometry "112 Bytes Sub-chunk Payload" from hard-coded fallbacks, indistinguishable from real readings. | `test_info_does_not_print_made_up_values_when_the_device_is_silent` | Print "not reported" instead of the fallbacks. **Real device:** it answers `0xAD` and `0x9E` with a bare `f0 70` ACK, so there is no firmware version, serial number or geometry to read; `info` shows hard-coded values for them. Worse, the `0xF1` reply to `0x81` is the hardware model descriptor (`50F`, PROTOCOL.md) and `parse_serial` prints it as "Serial Number" (`test_model_descriptor_is_not_labelled_serial_number`); the firmware line is the fallback `v2.0 (CMS-60D/PO-400 v2)` (`test_firmware_line_is_not_a_hard_coded_fallback`); the code ignores the `0xF1` reply because it checks `report[0] == 0x81`. PROTOCOL.md lists `80 00` -> `0xCF` as the firmware query, which the CLI never sends: `record_exchange.py --probe-firmware` records it. **FIXED in patch 0013:** `info` prints "not reported by the device" for firmware, serial, user profile and geometry when the device did not give them. The 0xF1 reply to `0x81` is shown as `Device Model Descriptor` (`50F`). (Correction to the first write-up: `parse_serial` was not involved; `50F` in the Serial Number line was the CLI's hard-coded fallback and only happened to equal the real descriptor.) The probe recording shows `80 00` is also answered with a bare ACK, so the device reports no firmware version at all. |
| **T5 Storage-frame checksum is never verified** | Every real `0xED` frame in the capture carries a correct 7-bit checksum, but the detector decodes frames with a wrong one. A corrupted frame silently yields wrong samples. | `test_frame_with_a_bad_checksum_is_rejected` | Drop (and count) frames whose checksum fails. Safe on the capture: all 12 frames pass. **FIXED in patch 0013:** The detector drops a series frame whose 7-bit checksum is wrong (event `CORRUPT_FRAME`); `download` then warns with the count. Samples after a dropped frame may be misaligned between the SpO2 and pulse series, so the warning tells the user to download again. |
| **T6 The page number is a sample offset, so downloads repeat the session** | A `9D 04` read's "page" argument is the offset, in raw samples, where the reply starts: offsets 0, 1, 2 return the same 214-sample session starting 0, 1, 2 samples in (214, 213, 212 values; reply k equals reply 0 from sample k, both series, verified). The engine treats it as the next page, so for a 107-record session (header 214) it asks for windows 0, 1 and 2 and exports 214 records: records 0..102 from window 0, 103..205 from window 1 (shifted by one raw sample, so the averaged pairs differ slightly), 206..213 from window 2. Anything after the first record is a repeat of the same minutes. | `test_download_today_returns_214_records_that_repeat_the_session_three_times_over` (characterisation), `test_each_sample_of_the_session_is_exported_once`, `test_the_page_number_is_a_sample_offset_each_reply_is_the_session_shifted_by_that_many_samples` | Unknown: what one reply holds at most (the recorded reply is the whole 214-sample session in 6 frames), the offset unit for longer sessions, and what the device sends past the end. Needs a longer recording and `record_exchange.py --probe-offsets` (read-only). Fix after T3: stop at the true record count and request the next window at offset = samples received. **FIXED in patch 0013:** The engine requests the next reply at offset `2 * records_so_far` (not page 1, 2, ...) and stops on a reply that adds no record. One reply covers the whole 214-sample session, so a download is now one window (7 commands plus ack). `tests/fixtures/probe.trace.json`: offset == stored samples gives an end marker, beyond it silence. **Confirmed on real multi-window data (psytrap, 2026-10-15):** a 937-record (~15.5 min) session downloaded as 937/937 records, 0 sequence gaps, 0 duplicate timestamps, uniform 1.00s spacing throughout -- across roughly 4-5 window-boundary transitions. |
| **T7 Storage geometry is the ACK byte** | The device answers `9E 40 04` with `f0 70`. `parse_storage_architecture_response` accepts `0xF0` and reads byte 1 (`0x70` = 112) as a chunk size, so `info` prints "112 Bytes Sub-chunk Payload", which is the ACK's status byte, not a geometry. | `test_geometry_is_not_derived_from_the_ack_byte` | Accept only `0x9E`/`0x9F`/`0xEF` replies; print "not reported" otherwise. **FIXED in patch 0013:** `parse_storage_architecture_response` accepts only `0x9E`/`0x9F` replies, no longer the `0xF0` ACK. |
| **T8 Linux `hid` backend's unlock/query gets no useful reply** *(open, found 2026-10-15, after patch 0013)* | On this Linux machine, `--backend hid` connects fine, but the unlock handshake and session-reset writes get **no reply at all** (not even an ACK), and the session query gets a bare ACK (`f0 70`) instead of `0xEC` data -- `sessions` then reports zero sessions. `--backend hidraw` on the *same device, same moment* works perfectly (107 records), and `--backend hid` on the real **Windows** laptop also worked perfectly with the identical Python-level code (G5/G6 above). So the shared code (`HidBackend`, the engine's command sequencing) is not at fault -- demonstrably fine on Windows. | Reproduced cold (not residual state from switching backends: a fresh 5s and a fresh 20s wait before trying `hid` alone both still fail the same way) and ruled out as a timing race (polled for a full 1s after the query write; the bare ACK arrives instantly, nothing ever upgrades to real data). The project's own `time.sleep()` values are deliberate, matched against the vendor pcap's timing, not the cause. **Likely needs a genuine USB re-enumeration (unplug/replug), not more elapsed time** -- untested, since that is not remotely automatable. | Open. Likely low real-world severity: `PACKAGING.md` already documents Linux `hid` as "selectable for cross-platform development/testing", not the real Linux path (`hidraw` is, and is extensively verified); real Windows users get native `hid.dll`-backed hidapi (verified working); macOS would get `IOHIDManager`-backed hidapi, structurally closer to Windows's native path than to Linux's libusb path, though **this is unconfirmed -- no macOS hardware has been tested.** Candidate causes, none yet checked: the `0x00` report-ID prepend framing interacting badly with libusb specifically, a libusb transfer-type quirk, or the kernel-driver-detach dance (`wait_for_hidraw_reattach`, commit `69bb1bb`) leaving the device in a state only a real re-enumeration clears. `fiedle400 selftest --backend hid` reproduces it in two lines instead of a manual trace. |

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
attached, installed, or happens to return right now. Not yet done.

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

- [x] B1–B7 landed as separate commits; G1–G4 green locally (0001: B1, B1b, B3; 0002: B2, B4, B5, B6; B7 local)
- [x] Phase 1: `bump_version.py patch`, run **once** → `0.1.1`
- [ ] Diff audit: `git diff --stat && git diff`, zero debris
- [ ] G5: built binary runs `info` / `sessions` on the real device (local only; Windows 8.1 done once)
- [ ] G6: live device tests pass (Linux: `hidraw` and `hid`; Windows: `hid`)
- [ ] G7: real-finger session downloaded and plotted; user acknowledged the plot
- [ ] Ring 0: annotated tag `v0.1.1` created locally
- [ ] Ring 1: workflow_dispatch dry run; all 3 binaries smoke-tested on their OS
- [ ] Ring 2: push tag; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256, `--version` = 0.1.1)
- [ ] Phase 2 (final step, after user review): `bump_version.py minor` → `0.2.0`
