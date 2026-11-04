# Protocol B: Contec CMS50F v3.7 / CMS50I / CMS50H Serial Protocol Specification

Bit- and byte-accurate wire protocol reference for the **second, unrelated** Contec protocol
documented in this repo ("protocol B" in `CMS50_COMPATIBILITY.md`), used by the CMS50F with
firmware 3.7, the CMS50I and the CMS50H. **Not implemented for download in `fiedle400`** (T-105
is on hold); `fiedle400` only probes for it, to tell a protocol-B device apart from a supported
one and refuse clearly instead of guessing (`fiedle400/serial_port.py::probe_cms50f37`,
`fiedle400/protocol/cms50f37.py`).

This is the wire-level sibling of `PROTOCOL.md` (which documents the PO-400's own protocol,
called "protocol C" below for contrast). See `CMS50_COMPATIBILITY.md` for which real-world
models (PO-250, PO-300, CMS50F/I/H, ...) speak which protocol -- that is still an open question
for PO-250/PO-300 (findings 6-8 there).

**Evidence.** *Src* = OSCAR source (`cms50f37_loader.cpp`, gitlab.com/CrimsonNape/OSCAR-code).
*Wire* = a 2014 third-party serial capture of a real CMS50F 3.7, decoded in
`CMS50_COMPATIBILITY.md` §6 (`archive/capture/cms50f37-2014/`, not in git). *RE* = static
analysis of `SpO2.exe` v3.1.0.1, bundled inside the "Smart Device Assistant" installer
(`archive/bruteforce/smart_device_assistant/`), done 2026-10-29. *Inferred* = concluded from the
above, not seen directly.

---

## 1. Core Framing Rules

1. **9-byte fixed-length requests**: `7D 81 [op] [user] [session] 80 80 80 80` (Src; Wire). Unlike
   protocol C, every byte after the `7D` prefix has **bit 7 set**, including the two unused
   argument slots, which are left at the padding value `0x80` rather than a 7-bit `0x00` (Src).
2. **No checksum.** Protocol C's mod-128 checksum byte has no equivalent here (Src; Wire). A
   corrupted request or reply has no way to be detected except by failing to match a known reply
   code/length.
3. **Replies are `[code] [high bits] [data...]`, length fixed per code** (Src, table below). Byte 0
   is the code (`0x00`-`0x1F`, i.e. always below `0x80`, the opposite of protocol C's `header >=
   0x80` rule). Byte 1's bit *k* is the real bit 7 of data byte *k* (stripped the same way
   protocol C strips data bit 7, but carried in a dedicated byte instead of being spread by
   position).
4. **Opcodes are protocol C's opcodes plus 0x80, mostly in a disjoint range.** A protocol-B request
   byte equals `0x80 | op`; the project's `fiedle400/protocol/cms50f37.py::build_command` stores
   the *unmasked* opcode (`A7`, `A8`, ...) and ORs in `0x80` when building the frame, matching how
   `CMS50_COMPATIBILITY.md` §1/§6 and OSCAR's source name these commands.

---

## 2. Command & Response Registry

### 2.1 Outbound Host Requests
| Opcode | Name | Reply code | Evidence | Description |
| :---: | :--- | :---: | :---: | :--- |
| `A7` | Stop stored stream | `0C` | Src; Wire | First half of the "hello" handshake |
| `A2` | Stop live stream | `0C` | Src; Wire | Second half of hello, sent right after `A7` |
| `A8` | Model query | `02` ×1-2 | Src; Wire; RE | `fiedle400`'s only probe command beyond hello |
| `A9` | Vendor query | `03` | Src; Wire | e.g. `"Contec"` |
| `AA` | Device ID (user-set name) | `04` | Src; Wire | **On the PO-400 this opcode is `FLASH_CLEAR`** (`PROTOCOL.md` §2.1) -- never send it to an unidentified device |
| `A0` | Version query | `06` | Src; Wire | Meaning unconfirmed (OSCAR: "get version") |
| `A3` | Session count | `0A` | Src; Wire | User 0's recording count |
| `A4` | Session duration | `08` | Src; Wire | Half-seconds (CMS50F) or quarter-seconds (CMS50I/H), see §4 |
| `A5` | Session start time | `07`, `12` | Src; Wire | Date frame then time frame |
| `A6` | Download session data | `0F` or `09` | Src; Wire | `0F` = CMS50F (3 samples/frame); `09` = CMS50I (1 sample + PI) |
| `AB` | Username query | `05` | Src; Wire | |
| `AC` | Perfusion-index-available query | `0E` | Src; Wire | |
| `AD` | User count | `10` | Src; Wire | |
| `AE` | **Erase a recording** | -- | Src | **Never sent by `fiedle400`; no code path can reach it (no engine exists)** |
| `AF` | Unknown | (none) | Wire | Sent in the capture's command sequence; no reply observed |
| `B0` | Device info | `11` | Src; Wire | Fields unknown |
| `B3` | Unknown | `13`, `14` | Wire | Blanks / zeros in the capture |

### 2.2 Reply Frame Lengths (by code, byte 0)
From OSCAR's length table, reproduced as `fiedle400.protocol.cms50f37.LENGTHS` (indexed by `code &
0x1F`); only non-zero entries are real reply codes:

| Code | Length | Meaning |
| :---: | :---: | :--- |
| `02` | 9 | Model (frame 1 of up to 2) |
| `03` | 9 | Vendor |
| `04` | 9 | Device ID |
| `05` | 9 | Username |
| `06` | 4 | Version |
| `07` | 8 | Session start date |
| `08` | 8 | Session duration |
| `09` | 6 | Sample data, CMS50I (1 sample + PI) |
| `0A` | 4 | Session count |
| `0C` | 2 | Hello ack |
| `0E` | 3 | Perfusion-index-available |
| `0F` | 8 | Sample data, CMS50F (3 samples) |
| `10` | 3 | User count |
| `11` | 9 | Device info |
| `12` | 8 | Session start time |
| `13`, `14` | 9 | Unknown |

---

## 3. Frame Splitting

`fiedle400.protocol.cms50f37.split_frames(buf)` cuts a raw byte stream into `Frame(code, data)`
objects (a frozen dataclass; see the module). This is internal to protocol B -- it is *not* the
protocol-agnostic interface between an engine and the CLI. That role belongs to
`protocol.models.DecodedPacket`, which protocol C's `SerialPacketDetector` already produces
directly from bytes (it has no separate raw-frame stage to name). A future `Cms50f37Engine`
would consume `Frame` objects internally and emit `DecodedPacket` instances outward, so the CLI
and export code need no protocol-specific branches.

Splitting proceeds as follows:

1. Scan forward one byte at a time; a byte is a frame start only if `code < 0x80` and
   `LENGTHS[code & 0x1F] != 0` (§2.2) -- unlike protocol C, there is no sync byte to anchor on, so
   a byte that happens to match a valid code by coincidence would be misread. This has not been
   seen in practice (Wire) but is an open risk noted in the code.
2. If the buffer does not yet hold the full frame length, stop and return the unconsumed tail as
   `rest`, to be prepended to the next read.
3. For a complete frame, restore bit 7 of each data byte from byte 1 (`hi`): data byte *k* becomes
   `(raw & 0x7F) | (0x80 if (hi >> k) & 1 else 0)`.

No resynchronization-by-scanning is needed beyond skipping one byte at a time, and no cross-frame
decode state is kept -- a material difference from protocol C's `SerialPacketDetector`
(`fiedle400/engine/detector.py`), which must resync on several possible sync bytes and tracks
state across frames for its nibble-packed, delta-encoded samples.

---

## 4. Sample Encoding

`A6`'s data frames (`fiedle400.protocol.cms50f37.samples`, Src):

- **Code `0F` (CMS50F)**: 3 samples per frame, each an independent `(SpO2, pulse)` byte pair --
  *not* nibble-packed or delta-encoded like protocol C's `0xED` subframes (`PROTOCOL.md` §3.5).
- **Code `09` (CMS50I)**: 1 sample plus a perfusion index (PI) byte, which `fiedle400`'s model
  does not keep.
- **No-reading sentinel**: `pulse == 0xFF`, `spo2 == 0`, `spo2 > 100` or `pulse == 0` all decode to
  `(None, None)` (Src/Inferred) -- a different sentinel scheme from protocol C's out-of-range
  127/255 markers (`PROTOCOL.md`, `fiedle400/engine/detector.py`).
- **Duration unit**: `A4`'s reported count is in **half-seconds for a CMS50F**, **quarter-seconds
  for a CMS50I or CMS50H** (`duration_divisor`, keyed off the model string from `A8`) -- unlike
  protocol C, which always reports whole seconds (`PROTOCOL.md` §1 rule 4).

---

## 5. Observed Command Sequences

### 5.1 Wire capture (2014, SpO2 Assistant 2.x downloading a real CMS50F 3.7)
`CMS50_COMPATIBILITY.md` §6 decodes the full exchange. Command order:
`A7 A2 A8 A9 AA B0`, then `A7 A2 A0 B0 AC B3 AD A3 AB A4 A5 AF A7 A2 A6`. SpO2 Assistant sets
115200 8N1 before the first request, switches to 19200 8O1 and back once without writing
anything, and repeats the `A7`/`A2` hello right before `A6`, matching OSCAR's `resetDevice()`.

### 5.2 Code path found in `SpO2.exe` v3.1.0.1 (RE, 2026-10-29)
Static analysis of the binary bundled in "Smart Device Assistant" (`archive/bruteforce/
smart_device_assistant/`) found **two separate command-send functions**:

- One (at a given build's `0x49baa9`) sends exactly protocol C's opcode set
  (`80-9F, A0-A3, A6, A7, BE`) -- confirmed identical to the already-documented 3.1.0.4 behavior.
- A second, distinct function (`0x4915c5`) sends `A0-AF, B0-B3, B7, B8` -- protocol B's command
  space. Its call sites fire `A7 A2 A0 B0 AC B3` in that exact order, matching the first six
  commands of the 2014 wire capture above almost verbatim.

**One unresolved discrepancy (RE, not explained):** the frame this second function builds starts
`7D 80 [opcode] ...` -- byte 1 is a literal, never-overwritten `0x80`, not the `0x81` the 2014
wire capture and OSCAR's source show. Confirmed by direct disassembly (the byte is written once,
at function entry, and never touched again before the frame is handed to the write call). This
may be a genuine variant, something resolved in a later encoding step not visible in this
function, or a different device/mode than the one captured in 2014. Treat as an open question,
not a correction to §1.1's `7D 81` rule, which rests on the Wire evidence.

This function's existence is the mechanical explanation for why a real PO-300 owner's device was
detected by "Smart Device Assistant" (which bundles this build) but not by plain "SpO2 Assistant"
(the 3.1.0.4 build, which only has the first function) -- see `CMS50_COMPATIBILITY.md` finding 6.

---

## 6. Differences from Protocol C (`PROTOCOL.md`), Summary

| | Protocol C (PO-400) | Protocol B (this document) |
| :--- | :--- | :--- |
| Transport | USB HID (`28E9:028A`) | USB-serial, 115200 8N1, or Bluetooth |
| Argument encoding | 7-bit | bit 7 forced set |
| Checksum | mod-128 | none |
| Reply header | `>= 0x80` | `< 0x80`, with a separate high-bits byte |
| Sample packing | nibble-packed deltas across frames | flat per-sample byte pairs |
| Duration unit | seconds | `A4`: bytes, 2 per 1 Hz sample (OSCAR: half-seconds on a CMS50F, quarter on a CMS50I) |
| Erase | `9D 7F` | `AE` |
| Opcode `AA` | `FLASH_CLEAR` | Device ID query |

---

## 7. Implementation Status in `fiedle400`

**The PO-250 is supported for download in this protocol (T-105, v0.5.9); untested on a real
PO-250.** Every other protocol-B device is refused.

- **Discovery** (`serial_port.py::probe_cms50f37`, `probe_any`): only after the protocol-C probe
  fails on a serial port. Sends the flush (`80`×7), hello (`A7`, `A2`), user count (`AD`) and
  model query (`A8`). The port counts as protocol B only if the hello comes back as `0C 80` and
  `AD` as a `0x10` frame, every byte after the code with bit 7 set
  (`split_frames(strict=True)`).
- **Model gate** (`protocol/cms50f37.py::is_refused_model`, psytrap 2026-11-04): a device whose
  `A8` reply starts with `CMS50` (CMS50F v3.7, CMS50I, CMS50H) is refused
  (`SerialBackend._refuse_cms50f37`). Any other answer, or none, is taken as a PO-250 and shown as
  "Pulox PO-250 (protocol B, …)" with its raw string. The PO-250's own string is unknown:
  kaivol/pulox never sends `A8`, and the 2014 capture is a CMS50F.
- **Engine** (`engine/cms50f37.py::Cms50F37Engine`, picked by `serial_engine.make_engine`):
  `info` (`A8`, `A3`), `sessions` (`A3`, then `A4` and `A5` per recording) and `download` (`A6`
  until the announced number of samples or 2 s of silence; a warning if fewer came, then `A7`).
  `A4` is a length in bytes, 2 per 1 Hz sample (41,808 → 20,904 samples, 5 h 48 m 24 s in the
  capture; kaivol reads `length / 6` frames of 3 samples).
- **Refused, never sent:** erase (`AE`), `AA`, clock (`read-time`, `set-time`), live mode
  (`detect`). `clear` is refused on every serial port anyway (T-104).
- **Tests:** `tests/test_protocol_b.py` replays the 2014 capture (1 recording, 2014-08-03
  03:18:48, 20,904 announced, 8,202 received, one warning); the serial emulator's default model
  serves the same data over a real pseudo-terminal (`tests/test_serial_emulator.py`).

---

## 8. Sources

See `CMS50_COMPATIBILITY.md` §7 for the forum/wiki sources behind the PO-250/PO-300 compatibility
question. This document's own sources are OSCAR's `cms50f37_loader.cpp`, the 2014 serial capture
(`archive/capture/cms50f37-2014/`, not in git), and the `SpO2.exe` v3.1.0.1 disassembly
(`archive/bruteforce/smart_device_assistant/`, not in git).
