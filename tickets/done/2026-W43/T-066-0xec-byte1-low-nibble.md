# T-066: Decode `0xEC` byte 1, bits 0..3

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `PROTOCOL.md` §3.2 (`0xEC` header), §3.5 (`0x9D` series types), §3.9 (`0xEF` mask)
  - `archive/bruteforce/SpO2.exe` (static analysis only)
  - `archive/capture/*.pcapng` (every recorded `0xEC` header)
  - `fiedle400/engine/device.py` (`clear_memory`), `fiedle400/protocol/commands.py`,
    `tests/test_clear.py` (found on the way, see below)

---

## Description & Context

Split out of [T-051](../../open/T-051-manual-mode-remaining-protocol-questions.md) on psytrap's
request (2026-10-21: "make this an independent ticket and investigate"). `PROTOCOL.md` §3.2 said
of `0xEC` byte 1: bits 0..3 are stored separately and compared with 1 to pick a download path,
meaning unknown, `0` in every recording (T-039). Byte 1's bit 6 (last header) was already known.

What was NOT known: what the value 1 changes in SpO2 Assistant's download, and whether any
recording ever had it.

---

## Criteria

- [x] Every `SpO2.exe` read of the stored nibble traced to what it changes
- [x] Every `0xEC` header in the captures checked
- [x] `PROTOCOL.md` updated with the result
- [x] `clear -s N` sends the vendor's whole delete-one sequence (found on the way)
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

Done 2026-10-21 (patch 0032). Static analysis of `SpO2.exe` plus a scan of every capture; no
device needed.

**Result: bits 0..3 = 1 means the recording has a third data series.** SpO2 Assistant then reads
it after SpO2 and pulse, with data type `0x03`. Any other value means SpO2 and pulse only. Every
PO-400 recording has 0.

Chain in `SpO2.exe`:
- `0x4ea405` (the `0xEC` case of the reply parser) stores `byte1 & 0x0F` at `+0x2f8`; getter
  `0x4c3c50`. Its only caller, `0x4b8ce3` in the recording-list dialog, sets the dialog flag
  `+0x11c` to `nibble == 1`. Each header overwrites it, so the last header listed decides.
- With the flag set, the download asks for a third series after the second one ends:
  `9D 7F 03 user entry 00 00` at `0x4b9f4c`, next to `9D 7F 01` after series 2 (`0x4b9e8c`), and
  `9D <mode> 03 user entry 00 00` at `0x4b984b` once all data is in. Send helper `0x4bc385`, `0x9D`
  case `0x4bc54b`: byte 1 = mode, byte 2 = type, bytes 3..4 = user and entry, bytes 5..6 = offset.
- Progress and buffer sizes use samples x 3 instead of x 2 when the flag is set (`0x4b7575`,
  `0x4b795e`, `0x4b7d42`, `0x4b9329`, `0x4b98a2`, `0x4b9dc8`): two series become three.
- The `0xED` data parser (`0x4ea735`) dispatches by data type: 1 to the SpO2 decoder `0x4e943d`,
  2 to the pulse decoder `0x4e97ce`, 3 to `0x4ec07a`.
- `0x4ec07a` uses the same subframe layout (base at byte 5, 13 delta bytes, 27 samples, nibble
  `0xF` invalid). It accepts 1..220 (`0xDC`), stores each value times 10 as a 16-bit number,
  with `0xFFFF` for invalid. Its uncompressed form (`0x4e9ea9`/`0x4e9b49`) keeps 10..2200
  (`0x898`).

What the third series measures is not stated in the code. The scale (0.1 steps up to 22.0) and
the strings `PI Graph Enabled` and `PI%` in `SpO2.exe` suggest perfusion index (PI) in percent.
That is an inference, not decoded.

A second source sets the same flag: in the download dialog (`0x4ba6c7`), when the `0xEF`
capability bytes have neither `0x40` nor `0x01` in their first byte, and bits 0 and 1 in their
third, the flag is that third byte's bit 4 (`0x10`). The recorded `0xEF` reply takes the `0x40`
path, so it never gets there.

Captures (strict 21-byte match with a valid checksum and `user` name), 11 headers:
`bum400.pcapng` (`00`, `40`), `bum400__2.pcapng` (`40`), `bum400_download.pcapng` (`00`, `00`,
`00`, `40`), `raw/bum400_raw.pcapng` (`00`, `00`, `40`), `realtime/bum400_realtime.pcapng`
(`40`). Bits 0..3 are 0 in all of them, and every `9D 04` download request asks for type 1 or 2
only. The Manual-mode capture has no `0xEC`.

**Found on the way: delete-one is a sequence, and erases have a reply.** The same reply-handler
code (`0x4b9e19`-`0x4ba07d`) shows that the vendor's Delete erases one *series* per command:
`9D 7F 02 user entry` (pulse) from the button, then, when the device answers
`ED 7F 02 user entry 00 chk` (status 0 = done), `9D 7F 01 user entry` (SpO2), then `9D 7F 03`
when the third-series flag is set. Delete-all is one command. The captures confirm the reply
shape: `ED 7F 7F 7F 7F 00 69` follows the delete-all in `bum400.pcapng` and
`raw/bum400_raw.pcapng` (PROTOCOL.md 3.13 said there was no reply). `fiedle400 clear -s N` sent
only the first command (0.4.29 to 0.4.37), so on a real device it may have erased only the pulse
series. It now sends `02` then `01`, reads the erase reply after each, and stops on a non-zero
status; the re-listing check stays. `tests/test_clear.py`: the sequence, a failed reply stops it,
the captured reply parses as done. Still never run on a real device: T-047's
`clear` check covers it.

`fiedle400` ignores bits 0..3 and reads SpO2 and pulse. For a recording with the flag set, that
still gets both series right and leaves out the third. No code change for the nibble: no PO-400 has shown it.
If one ever does, reading type 3 is a small addition (same decoder, other limits).
