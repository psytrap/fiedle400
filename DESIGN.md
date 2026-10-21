# fiedle400 — Architecture

How the code is organised and why. For the byte-level protocol see
[PROTOCOL.md](PROTOCOL.md); for rules that bind contributors (human or AI) see
[AGENTS.md](AGENTS.md); for the release process see [RELEASE_PLAN.md](RELEASE_PLAN.md);
for building installers see [PACKAGING.md](PACKAGING.md).

## 1. What it is

A command-line tool that talks to the Pulsox PO-400 / Contec CMS-50 pulse
oximeter (USB HID, VID `0x28E9`, PID `0x028A`). It lists and downloads the
sessions stored on the device, reads and sets its clock, and exports the data
as an HTML viewer page (default), `.SpO2`, CSV or JSON, and shows recordings already on disk (`view`). The package is
`fiedle400`; the *device* is still called PO-400 in user-facing text.

```
 device ──USB HID──> hid_driver ──reports──> engine ──records──> export ──> .html/.spo2/.csv/.json
                    (hidraw | hid)     (detector + device)          └──> recording (read back) ──> spo2_viewer (HTML)
                                            ▲
                          protocol (commands, parsers, models) ── cli (argparse, prompts)
```

## 2. Modules

| Module | Responsibility |
|---|---|
| `cli.py` | argparse, one `command_*` handler per subcommand, interactive wizard when started without arguments, `run_guarded` (any unexpected error → one-line message, exit 1; Ctrl+C → 130; `FIEDLE400_DEBUG=1` re-raises). Contains no protocol knowledge. |
| `hid_driver.py` | Finding and opening the device. `LinuxHidrawBackend` (`/dev/hidraw*`, stdlib only, default on Linux) and `HidBackend` (`import hid`, default on Windows and macOS). Also `find_pulsox_hid_devices` (sysfs scan). |
| `protocol/commands.py` | Builds outbound 64-byte reports (`0x7D 0x81 …`, checksummed). |
| `protocol/parsers.py` | Decodes inbound reports (session index `0xEC`, hardware ids, …) into `models`. |
| `protocol/decompression.py` | Decodes the 30-byte `0xED` storage frames (MSB mask bytes, run/escape coding) into SpO2 and pulse values. |
| `protocol/models.py`, `checksums.py`, `hardware.py` | Dataclasses (`SessionInfo`, `DecodedPacket`, …), checksum helpers, USB constants. |
| `engine/buffer.py` | Byte-stream buffer for serial-style reports. |
| `engine/detector.py` | `SerialPacketDetector`: turns raw reports into `DecodedPacket` events (live stream frames and stored `0xED` series frames). |
| `engine/device.py` | `SerialDeviceEngine`: the conversations with the device — handshake, list sessions, download one or all, set time, clear. |
| `serial_engine.py` | Backward-compatible re-export of `engine`. Import from `fiedle400.engine` in new code. |
| `export.py` | Writes records as an HTML viewer page (default), `.SpO2` (Contec binary, see SPO2_FORMAT.md), CSV or JSON. |
| `config.py` | Settings file (`%APPDATA%\fiedle400` or `$XDG_CONFIG_HOME/fiedle400`), working-directory resolution, `FIEDLE400_*` environment variables (legacy `PO400_*` still honoured). |
| `console.py` | Windows console encoding and window handling. |
| `recording.py` | Stdlib-only readers for `.spo2`, `.csv`, `.json` recordings on disk (`load_session_file`, `find_latest_session_file`); feeds `view`. Replaced `plot.py` (T-006, T-013). |
| `spo2_viewer.py` | Builds the self-contained HTML viewer page (chart, report, desaturation detection in JS, a port of `desat.py` that `tests/test_desat_js_parity.py` keeps in step). |

## 3. Download flow

1. `command_download` opens the device and builds a `SerialDeviceEngine`.
2. `list_sessions`: send the index request; each `0xEC` reply is one session
   (start time, header count). The header count is **samples, one per second**;
   one *record* is one sample (T-075).
3. `download_session`, per session: send `9D 04` reads (SpO2 series, pulse
   series). The argument is a **sample offset**, and each reply runs from that
   offset to the end of the stored data, in 30-byte `0xED` frames. The engine
   asks again at offset `2 * records_so_far` and stops when a reply adds
   nothing.
4. `SerialPacketDetector` validates each frame (7-bit checksum) and decodes
   it; out-of-range decoded values (SpO2 outside 1..100, pulse outside 1..254) mark a finger-out
   second. No real recording has contained one yet (T1, RELEASE_PLAN §3d).
   Corrupt frames are counted and reported, never silently dropped.
5. Records are merged into dicts (timestamp, SpO2, pulse, flags) and handed to
   `export`.

Downloading never modifies the device. `clear` is the only destructive
command; it needs confirmation (or `-y`) and must never be run by tests
against real hardware.

### 3a. Worked example: one real download, start to finish

The steps above as *bytes*, for a fast recap without re-reading
`PROTOCOL.md` cold. Chains real, already-verified wire data (sources
cited per step); invents nothing.

1. **Unlock.** One 64-byte write: `7D 81 A7` + six `0x80` key bytes,
   then immediately `7D 81 A2` (the storage-negotiation half), padded
   with `0x80` to 64 bytes total -- not two separate writes, and not
   `0x00` padding (PROTOCOL.md §3.1; a real test using the wrong
   padding/split got silence from the device). Reply: `F0 70`
   (`COMMAND_ACK`).

2. **Query the session index.** Request `9C 01` (opcode, user slot 1;
   checksum `0x1D` would be `(0x9C + 0x01) % 128`, though real traffic
   omits it -- PROTOCOL.md §3.2). The device answers with a 21-byte
   `0xEC` frame; a real one from the vendor capture:
   `EC 40 01 01 1A 09 06 0A 00 2E 73 01 00 00 75 73 65 72 00 00 42`.
   Decoded: flags `0x40` (data ready), date `1A 09 06` = 2026-09-06,
   time `0A 00 2E` = 10:00:46, sample count `73 01 00 00` (28-bit
   LE) = 243 samples, one per second: 243 one-second records, 4m 03s
   (PROTOCOL.md §1.4, T-075; CHANGELOG.md T3 had read it as 2 Hz).

3. **Read the SpO2 series.** Request `9D 04 01 01 01 [offset] 00 [chk]`
   -- mode "read block", type `0x01` (SpO2), offset starting at 0. The
   device replies with a stream of 30-byte `0xED` subframes until the
   stored data runs out. A real boundary probe (`tests/fixtures/probe.trace.json`,
   one 214-raw-sample session) showed the offset is a **sliding
   window into the whole series, not a page number**: requesting
   offset `k` returns `window(0)[k:]`, so the correct read starts at
   0 and continues at `offset = 2 * records_so_far` -- stepping it
   like a page index instead is exactly the bug that made a
   107-second session download as 214 padded, overlapping "records"
   (PROTOCOL.md §3.5, CHANGELOG.md T6). At `offset == stored_samples`
   the device sends one filler frame decoding to the `0xFF 0xFF`
   terminator; past that, nothing.

4. **Read the pulse series.** Same shape, type `0x02`.

5. **Decode each `0xED` frame.** Reassemble the 21 compressed data
   bytes (`0x08..0x1C`, each masked to 7 bits) with their separated
   MSBs (`0x05..0x07`, 7 bits each): `byte[i] = (msb_i << 7) | payload[i]`
   (PROTOCOL.md §3.5). Each reassembled byte holds two delta nibbles.
   A decoded value outside 1..100 (SpO2) or 1..254 (pulse) marks a
   finger-out second -- a code path that has never actually fired
   against real hardware yet (T1; `fiedle400` now prints a loud
   runtime alert the first time it does, `cli._probe_out_alert`).

6. **Merge and export.** SpO2 and pulse records pair up by sequence
   index into `{timestamp, spo2, heart_rate, flags}` dicts and go to
   `export.export_records` as `.spo2`/`.csv`/`.json`.

The Manual-mode recording uses its own commands (`0xA0`/`0xA3`/`0xA2`/`0xA7`,
PROTOCOL.md §3.14): `list_sessions` asks for its header only when the Auto list is empty, and
`download_session` hands a manual `SessionInfo` to `download_manual`
(`fiedle400/protocol/manual.py` decodes it). The records have the same shape as above.

## 4. Tests

Unit and simulator tests run anywhere with `python -m unittest discover -s tests`
(no hardware, no network, no non-stdlib packages required).

- `tests/hwsim.py` is a simulated device: `FakeOximeter` replays a recorded
  exchange (`tests/fixtures/*.trace.json`, real-device captures) through a fake
  `/dev/hidraw` tree (`HidrawSim`) or a fake `hid` module, with a
  `VirtualClock` so nothing really sleeps. `command_key` matches commands by
  meaning, not by raw bytes.
- `tests/test_device_live.py` needs a real device and runs only with
  `FIEDLE400_LIVE=1`; `fiedle400 selftest` is the read-only one-command check.
- `tests/capture_tools/` are developer scripts for decoding and recording
  captures, not tests.

Tests must not depend on the machine they run on: no real `/dev` or `/sys`,
no user config, no `FIEDLE400_*`/`PO400_*` variables (use `hwsim.scrub_env`).

## 5. Platform notes

- Linux default is `hidraw`; the `hid` (libusb) backend can detach the kernel
  driver and make `/dev/hidraw*` vanish while it holds the device.
- Windows and macOS use the `hid` backend. The PyPI name is a trap: the code
  uses `hid.Device` (PyPI `hid`) and falls back to `hid.device()` (PyPI
  `hidapi`); CI and the frozen binary install `hidapi`.
- The device does not report its clock: the `0xF2` reply is the same fixed bytes in every
  recording, so it is not decoded; `read-time` prints it raw (PROTOCOL.md §3.3). Stored
  sessions carry their own, correct timestamps.
