# fiedle400 — Architecture

How the code is organised and why. For the byte-level protocol see
[PROTOCOL.md](PROTOCOL.md); for rules that bind contributors (human or AI) see
[AGENTS.md](AGENTS.md); for the release process see [RELEASE_PLAN.md](RELEASE_PLAN.md);
for building installers see [PACKAGING.md](PACKAGING.md).

## 1. What it is

A command-line tool that talks to the Pulsox PO-400 / Contec CMS-50 pulse
oximeter (USB HID, VID `0x28E9`, PID `0x028A`). It lists and downloads the
sessions stored on the device, reads and sets its clock, and exports the data
as `.SpO2`, CSV or JSON (and optionally a PNG plot). The package is
`fiedle400`; the *device* is still called PO-400 in user-facing text.

```
 device ──USB HID──> hid_driver ──reports──> engine ──records──> export ──> .spo2/.csv/.json
                    (hidraw | hid)     (detector + device)          └──> plot (PNG, optional)
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
| `export.py` | Writes records as `.SpO2` (Contec binary, see SPO2_FORMAT.md), CSV or JSON. |
| `config.py` | Settings file (`%APPDATA%\fiedle400` or `$XDG_CONFIG_HOME/fiedle400`), working-directory resolution, `FIEDLE400_*` environment variables (legacy `PO400_*` still honoured). |
| `console.py` | Windows console encoding and window handling. |
| `plot.py` | Optional PNG plot; imports matplotlib lazily and prints an install hint if absent. |

## 3. Download flow

1. `command_download` opens the device and builds a `SerialDeviceEngine`.
2. `list_sessions`: send the index request; each `0xEC` reply is one session
   (start time, header count). The header count is **raw 2 Hz samples**; one
   *record* is the average of two raw samples, so records = `(raw + 1) // 2`.
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
