# T-101: Download stored recordings from PO-250/PO-300 (no live/realtime mode)

- **Status:** Done
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Depends on:** [T-104](T-104-detect-po250-po300-po400-for-wizard-and-info.md) (detection)
- **Scope & Relevant Files:**
  - `fiedle400/engine/`, `fiedle400/hid_driver.py`; a serial transport next to it if needed
  - `PROTOCOL.md` §5, `README.md`

---

## Description & Context

Scope set by psytrap (2026-10-29): "download recording from device is the task",
"no live recording", "Only download recordings". `sessions` and `download` (and
the wizard) for the stored recordings of these models; no live or realtime
streaming, no erase.

What T-098 and T-100 settled (`PROTOCOL.md` §5): SpO2 Assistant sends the
PO-400's command frames unchanged over HID and over USB-serial (115200 baud),
and picks devices only by USB ID. The PO-250 ships with SpO2 Assistant; the
PO-300 has the PO-400's Auto and Manual storage modes. So:
- **HID model** (`28E9:028A` or `0483:5751`): the existing engine, with the
  extra ID accepted. Probably little more than that.
- **USB-serial model** (`10C4:EA60`, `1CBE:0002`, `0483:5740`, or STM32/USB
  ports): a serial transport under the existing engine, same commands and
  parsers. The shipped binary stays zero-dependency, so no `pyserial`: `termios`
  on Linux/macOS, the Win32 COM API through `ctypes` on Windows.
- Where the model's replies differ (model string, `0xEF` capability bytes,
  memory layout), branch on the model string from T-104, not on the USB ID.

OSCAR's CMS50F v3.7 loader uses the same opcodes with the `7D 81` prefix that
`fiedle400` already sends (PROTOCOL.md §1.6), so it is the same family, not a
fallback protocol (corrected 2026-10-29).
OSCAR divides the CMS50F v3.7 session duration by 2 and the CMS50I's by 4
(`duration_divisor`); after T-075 do not copy that without evidence.

Without hardware this is mock-tested only; the first run on a real device is
the test (T-102).

## Criteria

- [x] Transport for the model chosen from T-104's report (HID ID added, or serial transport):
      both, since no owner has reported yet
- [x] `sessions` and `download` for that model, read-only (no erase, no live mode)
- [x] Mock tests built from `PROTOCOL.md`; `README.md` says "untested on real
      hardware" until an owner confirms
- [x] Tests pass

## Execution Notes

Done 2026-10-29 (cloud, with T-104; patch 0036). No device: mock tests only.

- **HID:** the device search takes both HID IDs SpO2 Assistant scans (`28E9:028A`,
  `0483:5751`; `protocol.hardware.HID_USB_IDS`), in the hidraw sysfs scan and in `hid.enumerate`.
- **Serial:** new `fiedle400/serial_port.py`, `SerialBackend` with the HID backends' interface,
  so the engine, `sessions`, `download` and the wizard run on it unchanged. Standard library
  only: termios on Linux/macOS, Win32 COM API via ctypes on Windows. 115200 baud (SpO2.exe),
  8N1, no flow control. Writes drop the HID padding (`unpad_report`); reads cut the byte stream
  at 10 ms quiet gaps or 64 bytes. Ports are found by USB ID through sysfs (Linux) and the
  registry (Windows); on macOS `--device /dev/cu.…`.
- **Selection:** `-b serial`, a serial `--device` path (`/dev/ttyUSB*`, `/dev/ttyACM*`,
  `/dev/cu.*`, `COMn`), or automatic: with no backend or device given, "no HID device found"
  falls back to a serial candidate if one exists.
- **Probe before use** (psytrap, 2026-10-29: "Can it distinguisch between regular serial
  device and po serial device" -> "do it"): the USB IDs `10C4:EA60` and `0483:5740` are generic
  (CP210x, STM32), so every serial candidate is opened and sent the unlock and `81 01`, the two
  read-only commands `info` starts with. Only a port that answers with a valid `0xF1` model frame
  within 0.3 s is used; others are closed and named as skipped. Several answering ports: the
  first is used and the others named. None: an error naming every port. An explicit `--device`
  that stays silent is used anyway, with a warning. The generic HID ID `0483:5751` is probed the
  same way; `28E9:028A` is not, and hidraw tries PO-400 nodes first.
- **No erase:** `clear` and the wizard's erase are refused unless the device is on the PO-400's
  USB ID `28E9:028A`; nothing is sent.
- **Review (patch 0037, v0.5.3):** a line-by-line review of the new transport code fixed five bugs before
  any hardware saw it: short or `EAGAIN` writes on POSIX (now retried for up to 1 s), Win32
  calls without `argtypes` (64-bit handles were truncated), stale COM ports from the registry
  (now filtered by `HARDWARE\DEVICEMAP\SERIALCOMM`), a probe drain that could spin forever on a
  streaming device (now at most 16 reads), and the hidapi open without a path using only the
  PO-400 ID. Each has a test. Not fixed, noted for T-102: the 10 ms quiet gap may be short for
  slow USB-serial adapters, ModemManager may grab a `ttyACM` port on Linux, `selftest` does not
  cover serial, and some messages still say "Pulsox PO-400" for every model.
- **Tests:** `tests/test_serial_port.py` (34): padding rules, sysfs and registry discovery, the
  real termios setup against a pty, `sessions`/`download`/`info` over a simulated serial port
  that replays the PO-400 trace in 7-byte and 1-byte pieces, CLI backend choice and fallback,
  erase refusal, and the probe (silent, garbage, bad-checksum and answering ports, several
  candidates, explicit device, generic HID ID). Full suite: 457 tests, OK (13 skipped).

Left out / unknown: whether a real serial model answers like the simulated PO-400, the real
serial byte format and DTR/RTS needs, and the Windows serial code path (never run). T-102
(an owner) is the test.
