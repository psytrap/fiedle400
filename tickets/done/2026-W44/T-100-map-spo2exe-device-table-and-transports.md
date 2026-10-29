# T-100: Map `SpO2.exe`'s device table and its serial path

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Scope & Relevant Files:**
  - `archive/bruteforce/SpO2.exe` (static analysis)
  - `PROTOCOL.md` (new appendix: other devices)

---

## Description & Context

`SpO2.exe` is not PO-400-only. Found on 2026-10-29 (strings, not yet traced):
- Connection classes `HidConnection`, `ComConnection`, `BthConnect`,
  `SocketConnect` (threads `ThrdHidCon`, `ThrdComCon`, `ThrdBthCon`,
  `ThrdSocketCon`) and one protocol class, `YhjProtocol`.
- The command send helper (`0x4bc385`) builds the frame, optionally passes it
  through `0x57f0c8`, and queues it at `+0x15a0`; it does not write to a
  transport itself.
- COM port scan (`HARDWARE\DEVICEMAP\SERIALCOMM`) with USB IDs (`0x5f26e8`):
  `10C4:EA60` (Silicon Labs CP210x, as in OSCAR's CMS50F v3.7 loader),
  `0483:5740` ("STM32"), `1CBE:0002`, `0451:16AA`.
- HID IDs (`0x5f2e58`): `0483:5751` and `28E9:028A` (the PO-400).
- A "50K" family (ECG, PM10, step counter, single SpO2 spot checks) and BLE.

Open question: do serial devices get the same commands and replies as the
PO-400 (`9D`, `EC`, `ED` ...), or OSCAR's `7D 81 ...` framing
(`cms50f37_loader.cpp`)? If the same, downloading recordings from those models
(T-101) is mostly a USB-serial transport under the existing engine.

## Criteria

- [x] Which `Connection` subclass each USB ID selects, and what model/name the
      program attaches to it (none: the IDs only pick ports, see notes)
- [x] Whether `ThrdComCon` sends the same frames as `ThrdHidCon` (what
      `0x57f0c8` does, and when)
- [ ] Any model-specific branches in the download (`0xEF` capability bytes,
      `0xF1` model string such as `50F`) -- not traced; the model is not known from the USB
      ID, so this matters only once a real model string is seen (T-104)
- [x] `PROTOCOL.md` appendix with the result; T-061 updated

## Execution Notes

Done 2026-10-29 (cloud, static analysis of `archive/bruteforce/SpO2.exe` with capstone; no
device). Details and addresses are in `PROTOCOL.md` §5.

- **One connect routine scans HID and serial together** (`0x504f6f`): first the HID list
  (`0x47c833`: `0483:5751` and `28E9:028A`, both added to the same list, no per-ID model), then the
  COM ports (`0x47acc6`) at **115200 baud** (`0x1C200`, `0x50501c`).
- **COM port filter** (`0x47acc6` -> `0x47abf7`), list 1: `10C4:EA60` (CP210x), `1CBE:0002`,
  any port whose name contains `STM32`, `0483:5740` (STM32 virtual COM), any port named `USB`;
  list 2, kept apart: `0451:16AA` (TI's CC254x USB dongle, i.e. the Bluetooth LE path).
  No model name is attached to any ID; the model comes from the device's own replies.
- **Same bytes on every transport.** `YhjProtocol`'s send helper (`0x4bc385`, commands
  `0x83..0xBE`) builds the frame without knowing the transport and puts it into a byte queue.
  `ThrdHidCon` (`0x554c92`) and `ThrdComCon` (`0x554067`) are the same loop: take bytes from
  the queue, write them. HID writes them raw after report ID 0 (`0x47f645`), serial writes them
  raw with `WriteFile` (`0x41e608`).
- **`0x57f0c8` is not a transport step.** It appends a 16-bit check value and pads to 8 bytes
  (an encryption wrapper). It runs only when the setting `CustomProtocolInfo` in section `YHJ`
  is on (`0x52e48d`, read once), next to Bluetooth settings such as `SearchMinRSSI`; the PO-400
  traces never show it.

**Answer to the open question:** a USB-serial model under SpO2 Assistant gets the PO-400's
commands (`9D`, `EC`, `ED` ...), not OSCAR's `7D 81` framing. For T-101 that means a serial
transport (115200 baud on the IDs above; byte format not traced) under the existing engine, not a new protocol.
