# fiedle400: Test & Release Plan

> **Scope:** First tagged release of the `fiedle400` CLI (GitHub Release with Linux, Windows and macOS binaries)
> **Cadence:** Two-Phase Version Bump (Patch Pre-Flight • Minor Post-Shipment), adapted from the RefDiff rollout plan
> **Baseline:** `0.1.1` (Phase 1 done; no git tags exist yet; `master` had 25 commits at `0ab3bf0`, before patches 0005+)
> **Status:** Strategy approved by psytrap (2026-10-15). All blockers B1–B7 are resolved: B1, B1b and B3 via patch 0001 (applied locally and tested on real hardware by psytrap, 2026-10-15), B2, B4, B5 and B6 via patch 0002, B7 locally. Binary and installer verified on a real Windows 8.1 machine with the device attached. Nothing has been tagged or released. The `fiedle400` rename (§3b, patch 0010) lands after the `v0.1.1` tag.
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
fiedle400 download -o output/rc.spo2 && fiedle400 plot output/rc.spo2   # G7: visual acknowledgment
```

| Gate | Check | Today |
|:---|:---|:---|
| **G1 Mock suite** | `python3 -m unittest discover tests`: 0 failures, 0 errors. The only skips allowed are the 7 opt-in live-device tests (plus the plot tests when matplotlib is absent); the count must not vary with device state. | ✅ 157 run / 7 skip (live device only) with matplotlib, after patches 0005–0007. |
| **G2 Capture regression** | `test_pcap_decoder` actually runs against `analysis/bum400_20260906_100516.pcap` (it must not skip). | ✅ Runs and passes (B2). |
| **G3 Version sync** | `tests/test_version.py`: `fiedle400.__version__` equals `pyproject.toml` version; `fiedle400 --version` prints it; bump script cycle works. | ✅ Passing. |
| **G4 Zero-dependency promise** | In a clean venv with no third-party packages, `python3 -m fiedle400 --help`, `info`, `sessions` and `download` import and run. `plot` prints an install hint and exits 1. | ✅ Verified in a clean venv: 107 tests run, 0 failures (plot tests skip). |
| **G5 Binary build** *(local only)* | `pyinstaller fiedle400.spec` succeeds, **and the built artifact runs a device-touching command** (`info`, then `sessions`) with a real PO-400 attached; for Windows, the installed binary from the installer. `--version`/`--help` alone are not enough: a binary that starts but cannot load the `hid` extension passes them (this happened before `0ab3bf0`). CI runners have no oximeter, so this gate can only run on psytrap's machines; CI only proves the build succeeds. | ✅ Binary and installer verified on Windows 8.1 (`info`, `sessions` on the live device). Re-run on each RC build. |
| **G6 Live hardware** *(mandatory, the analogue of RefDiff's live CDP invariant)* | `FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live` passes with a real PO-400 attached, on Linux with **both** backends (`hidraw` and `hid`); elsewhere with `hid` only (`hidraw` raises off Linux by design, and the Linux-only tests skip with a reason). Never run two live runs at once (a lock file serialises them). | ✅ Windows criterion passes (`fiedle400 info` on a real 8.1 machine). Re-run the live suite on the RC: Linux both backends, Windows `hid` (needs patch 0006). |
| **G7 Visual & data acknowledgment** | Record a short session **with a finger on the probe**, download it to `.spo2`, `.csv` and `.json`, run `fiedle400 plot`, and have the user confirm the PNG looks physiologically plausible. Per `.agents/rules/implausible_data_warning.md`, constant 95/64 or 99/95 values with probe-out flags fail this gate. | Manual. |
| **G8 Output location** | Per `AGENTS.md`, output goes to the current directory (or the configured workdir), never a hard-coded `output/`; help strings say the same. | ✅ The code always wrote to the cwd; only the help strings said `output/`. Fixed in `9647913`. |

---

## 3. Release Blockers (fix before Phase 1)

Each blocker is a small, separate commit, landed **before** the patch bump.

| ID | Problem | Evidence | Fix |
|:---|:---|:---|:---|
| **B1** ✅ | matplotlib is a hidden hard dependency | `fiedle400/__init__.py:15` imports `plot` eagerly, so every `from fiedle400 import ...` (including `cli.py:24`) pulls in matplotlib. `cli.py:42` already imports `plot` lazily, so the eager import defeats that. | Done: `plot_session` is resolved lazily via `__getattr__`; `plot = ["matplotlib"]` extra added; `fiedle400 plot` prints an install hint when matplotlib is missing. |
| **B1b** ✅ | The release binary would crash on start | `.github/workflows/build-release.yml` installs only `pyinstaller hidapi`. Because of B1, the frozen binary would raise `ImportError` on every command (inferred, not yet built). | Fixed by B1. **Decision (psytrap): plot is not shipped in the binary.** `fiedle400.spec` excludes matplotlib. **Graceful failure (psytrap):** every command now runs through `cli.run_guarded`, which turns unexpected errors into a one-line message and exit code 1 (Ctrl+C → 130); `FIEDLE400_DEBUG=1` shows the full traceback. |
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

| Area | Renamed | Kept as is |
|:---|:---|:---|
| Package, entry point | `fiedle400/`, `fiedle400` command, `python -m fiedle400`, `prog` names | |
| Packaging, CI | `fiedle400.spec`, `fiedle400.bat`, `packaging/windows/fiedle400.iss`, release asset names | |
| Settings | `%APPDATA%\fiedle400`, `$XDG_CONFIG_HOME/fiedle400` | An existing `po400/config.json` is copied over on first read; the old file stays. |
| Env vars | `FIEDLE400_LIVE`, `FIEDLE400_DEBUG`, `FIEDLE400_WORKDIR` | The `PO400_*` names still work when the new ones are unset. |
| Installer | App name `fiedle400 (PO-400 Oximeter)`, folder `Programs\fiedle400` | Same `AppId`, so it **upgrades** a po400 install: it removes the old program folder and context-menu keys. Start Menu shortcut "PO-400 Oximeter" and `Documents\PO-400` stay. |
| Device-facing names | | "PO-400" in docs and output, `po400_…` recording filenames, udev rule filenames, `analysis/`, `handoff/` history |

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

**TODO (not yet done):** record a 5-10 minute session (`record_exchange.py`'s
default `download`, finger held on the probe throughout) to see how the
sliding-window offset (T6) behaves once a session spans more than one reply --
needs someone at the physical device for several minutes, not a scriptable
read-only step. Requested by the cloud in `handoff/trace-response.md`.

**Status: T1 to T7 are fixed in patch 0013 (the tests that pinned them now assert the correct behaviour). The Next step column keeps the original proposals; each row ends with what was done.**

| # | Finding | Evidence | Next step |
|:--|:---|:---|:---|
| **T1 Status flags read from the MSB mask byte** | `engine/detector.py` takes `flags = chunk[7]` of every 30-byte `0xED` frame, but PROTOCOL.md 3.5 defines byte 7 as the third MSB mask (`m2`), not a status field. Whenever a data byte in positions 22..28 has bit 7 set (every `0xF_` baseline escape does), `m2` is non-zero and the frame is reported as `searching`/`low-perfusion`. `engine/device.py` then stores those samples as `None`. | In the capture the last frame of each page (seq 5, `m2` = `0x60`) decodes as `searching,low-perfusion`; a download keeps 103 of 122 records and blanks the last 19. The other frames decode as `ok`. | **Confirmed on the real device** (`test_the_last_frame_of_a_window_is_read_as_probe_out_today`, `test_no_samples_are_lost_at_the_end_of_a_window`): each reply ends with a short filler frame (seq 5, 8 raw values) whose mask bytes are `0x7f`; byte 7 = `0x7f` reads as `probe-out,searching,low-perfusion`, so its 4 averaged pairs are not decoded (103 of 107 per reply, no `None` samples because the frame is skipped, not blanked). The CLI's "103/214 records" at the halfway checkpoint is this plus T6. **Unblocked (psytrap, 2026-10-15): proceed, flagged for double-checking rather than gated.** Byte 7 is `m2` (§3.5), not a status field, and the storage stream's own documented finger-out signal is different: a sentinel in the decoded value itself (`analysis/bum400_20260906_100516.md` §4 -- SpO2 out of range -> `0x7F`/127, pulse out of range -> `0xFF`/255), not a flag byte. Stop deriving probe-out from byte 7 for `0xED` frames; use the documented sentinel values instead. Re-verify against the 5-10 minute recording (TODO above) once it exists, and against the real serial-stream devices if any are available -- this device only exercises the storage path. **FIXED in patch 0013:** Both frames and flags: `engine/detector.py` no longer takes status flags from byte 7 of `0xED` series frames; a reply's short final frame (ends with the `0xFF 0xFF` terminator) is decoded like any other; out-of-range values (SpO2 127, pulse 255) mark the second as a finger-out record (`flags` = `probe-out`, SpO2 and pulse empty). Legacy single-sample frames keep their flag handling. **Flagged for double-checking (psytrap):** re-verify against the 5-10 minute recording and a real serial-stream device. |
| **T2 Silent device counts as a successful download** | With every reply dropped, `download` prints "No active session table returned; defaulting to downloading Session #1", saves an empty file and exits 0. | `test_device_that_never_answers_is_not_reported_as_a_successful_download` | Exit non-zero (and write no file) when no session answered or zero records came back. **FIXED in patch 0013:** `download` prints "No recording data was received from the device, so nothing was saved" and exits 1 without writing a file. |
| **T3** ✅ **confirmed** -- Session length is shown about twice too long | The header count (243) is raw 2 Hz values (`analysis/bum400_20260906_100516.md` section 5: 243 values = 122 s) and an independent decompression gives 243 values per series. `SessionInfo` treats it as seconds, so `sessions` shows 4m 03s for a 122 s recording and the engine never reaches its record target (it asks for page 1 and retries). PROTOCOL.md 3.2 and 1 also said "seconds" -- that mislabel is now fixed. **Mechanism confirmed by psytrap (2026-10-15):** the device genuinely takes two independent raw half-second readings per second -- not duplicates -- and the firmware/decoder average them into one physiological 1 Hz value. That is why the raw header count is exactly double the real duration: it counts the two half-second readings separately, before they are merged. Not a decode bug, a label bug -- the merge-by-averaging the decoder already does (`detector.py`: `round((v1+v2)/2.0)`) is correct and matches `analysis/bum400_20260906_100516.md` section 5's own description of the firmware behaviour. | `test_header_count_is_in_raw_2hz_samples_so_duration_is_about_two_minutes` (pcap, 243 -> 122 s), `test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds` (real, 214 -> 107 s) | Treat the header value as 2 Hz samples (duration = count // 2) in `SessionInfo`/the engine's record-count target. PROTOCOL.md §1 and §3.2 are fixed; §3.5.3 now states the confirmed merge mechanism. No decoder change needed -- the averaging was already correct, only the field's label and the duration/count math around it were wrong. **FIXED in patch 0013:** `parse_session_index_table` reads the 0xEC count as raw samples: `SessionInfo.raw_samples` = count, `record_count` = `duration_sec` = `(count + 1) // 2` (an odd count keeps its last reading: 243 -> 122, matching the 122 records decoded from the capture). Decoder unchanged. |
| **T4 `info` prints made-up values** | When the device does not answer, `command_info` still prints firmware "v2.0", serial "50F", user "user" and geometry "112 Bytes Sub-chunk Payload" from hard-coded fallbacks, indistinguishable from real readings. | `test_info_does_not_print_made_up_values_when_the_device_is_silent` | Print "not reported" instead of the fallbacks. **Real device:** it answers `0xAD` and `0x9E` with a bare `f0 70` ACK, so there is no firmware version, serial number or geometry to read; `info` shows hard-coded values for them. Worse, the `0xF1` reply to `0x81` is the hardware model descriptor (`50F`, PROTOCOL.md) and `parse_serial` prints it as "Serial Number" (`test_model_descriptor_is_not_labelled_serial_number`); the firmware line is the fallback `v2.0 (CMS-60D/PO-400 v2)` (`test_firmware_line_is_not_a_hard_coded_fallback`); the code ignores the `0xF1` reply because it checks `report[0] == 0x81`. PROTOCOL.md lists `80 00` -> `0xCF` as the firmware query, which the CLI never sends: `record_exchange.py --probe-firmware` records it. **FIXED in patch 0013:** `info` prints "not reported by the device" for firmware, serial, user profile and geometry when the device did not give them. The 0xF1 reply to `0x81` is shown as `Device Model Descriptor` (`50F`). (Correction to the first write-up: `parse_serial` was not involved; `50F` in the Serial Number line was the CLI's hard-coded fallback and only happened to equal the real descriptor.) The probe recording shows `80 00` is also answered with a bare ACK, so the device reports no firmware version at all. |
| **T5 Storage-frame checksum is never verified** | Every real `0xED` frame in the capture carries a correct 7-bit checksum, but the detector decodes frames with a wrong one. A corrupted frame silently yields wrong samples. | `test_frame_with_a_bad_checksum_is_rejected` | Drop (and count) frames whose checksum fails. Safe on the capture: all 12 frames pass. **FIXED in patch 0013:** The detector drops a series frame whose 7-bit checksum is wrong (event `CORRUPT_FRAME`); `download` then warns with the count. Samples after a dropped frame may be misaligned between the SpO2 and pulse series, so the warning tells the user to download again. |
| **T6 The page number is a sample offset, so downloads repeat the session** | A `9D 04` read's "page" argument is the offset, in raw samples, where the reply starts: offsets 0, 1, 2 return the same 214-sample session starting 0, 1, 2 samples in (214, 213, 212 values; reply k equals reply 0 from sample k, both series, verified). The engine treats it as the next page, so for a 107-record session (header 214) it asks for windows 0, 1 and 2 and exports 214 records: records 0..102 from window 0, 103..205 from window 1 (shifted by one raw sample, so the averaged pairs differ slightly), 206..213 from window 2. Anything after the first record is a repeat of the same minutes. | `test_download_today_returns_214_records_that_repeat_the_session_three_times_over` (characterisation), `test_each_sample_of_the_session_is_exported_once`, `test_the_page_number_is_a_sample_offset_each_reply_is_the_session_shifted_by_that_many_samples` | Unknown: what one reply holds at most (the recorded reply is the whole 214-sample session in 6 frames), the offset unit for longer sessions, and what the device sends past the end. Needs a longer recording and `record_exchange.py --probe-offsets` (read-only). Fix after T3: stop at the true record count and request the next window at offset = samples received. **FIXED in patch 0013:** The engine requests the next reply at offset `2 * records_so_far` (not page 1, 2, ...) and stops on a reply that adds no record. One reply covers the whole 214-sample session, so a download is now one window (7 commands plus ack). `tests/fixtures/probe.trace.json`: offset == stored samples gives an end marker, beyond it silence. Still open: sessions longer than one reply (needs the 5-10 minute recording). |
| **T7 Storage geometry is the ACK byte** | The device answers `9E 40 04` with `f0 70`. `parse_storage_architecture_response` accepts `0xF0` and reads byte 1 (`0x70` = 112) as a chunk size, so `info` prints "112 Bytes Sub-chunk Payload", which is the ACK's status byte, not a geometry. | `test_geometry_is_not_derived_from_the_ack_byte` | Accept only `0x9E`/`0x9F`/`0xEF` replies; print "not reported" otherwise. **FIXED in patch 0013:** `parse_storage_architecture_response` accepts only `0x9E`/`0x9F` replies, no longer the `0xF0` ACK. |

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
