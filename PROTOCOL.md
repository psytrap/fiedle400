# Pulox PO-400 / Contec USB-HID Protocol Specification

Bit- and byte-accurate wire protocol reference for the Pulox PO-400 (`VID_28E9&PID_028A`) pulse oximeter, reverse-engineered from `SpO2.exe` v2.0 and verified on USB bus captures and live hardware.

---

## 1. Core Framing Rules

1. **7-Bit Payload Restriction**: Data bytes carried in payloads must not set bit 7 (`0x00`..`0x7F` / 0..127) for UART backward compatibility and opcode avoidance. In `0xED` subframes, Bit 7 of the 21 payload bytes is stripped and stored across separated MSB bytes 5, 6, and 7 (`m0`, `m1`, `m2`).
2. **Modulo-128 Checksum**: All request and subframe packets use a 7-bit additive checksum:
   `checksum = sum(bytes[0..N-1]) % 128` (or `sum(bytes[0..N-1]) & 0x7F`)
3. **14-Bit Integer Packing (7-bit Little-Endian)**:
   `value_14 = byte[0] | (byte[1] << 7)`
4. **28-Bit Integer Packing (Raw Sample Count in 0xEC Header)**:
   `value_28 = b0 | (b1 << 7) | (b2 << 14) | (b3 << 21)` -- counts raw 2 Hz half-second samples, **not** seconds or 1 Hz records (confirmed: psytrap, 2026-10-15; see §3.2, §3.5 "Delta-Nibble Decompression" step 3, and CHANGELOG.md T3). Records (= seconds) = `(value_28 + 1) // 2`: an odd count keeps its last raw sample as a record of its own (the vendor capture's header says 243 and the session has 122 records, the 122 rows in `analysis/bum400_20260906_100516.md` §6, which `fiedle400` reproduces exactly).
5. **USB HID Report Size**: Outbound and inbound reports are 64 bytes fixed-length (`REPORT_SIZE = 64`), zero-padded.
6. **Two request framings, both accepted**: the vendor tool sends requests bare (`9C 01 1D`, zero-padded); `fiedle400` wraps most of them as `7D 81 <opcode> <args>` padded with `0x80` (`commands.build_hid_command`). The device answers both the same way (compare `analysis/bum400_20260906_100516.pcap` with `tests/fixtures/cli-exchange.trace.json`). Both tools send `0x82` and the `0x9D` storage commands bare.
7. **Replies are self-delimiting frames**: each reply has its own length (see §2.2) and ends with a checksum over the bytes before it (rule 2). The checksum is the reliable end marker: trailing zeros can be part of a frame (`FE 07 00 00 05`).

---

## 2. Command & Response Registry

> [!IMPORTANT]
> **Universal Protocol Principle: MSB Control vs. Data Distinction**
> Across the entire protocol, the Most Significant Bit (Bit 7) serves as the universal delimiter between control and data:
> - **`MSB = 1` (`0x80..0xFF`)**: **Opcode / Control Character** — All host request opcodes, device response markers, frame sync headers, and in-stream control escapes strictly have Bit 7 set.
> - **`MSB = 0` (`0x00..0x7F`)**: **Data Payload** — All parameters, counters, checksums, and in-stream payload bytes are restricted to 7 bits (masked with `0x7F`) to prevent accidental collisions with opcodes or frame boundaries.

**Evidence column.** *Vendor* = the vendor tool's own traffic in `analysis/bum400_20260906_100516.pcap`;
*CLI* = `fiedle400`'s traffic with the real device in `tests/fixtures/cli-exchange.trace.json` and
`tests/fixtures/probe.trace.json`; *RE only* = taken from the `SpO2.exe` disassembly and never seen on
the wire. Bytes are shown without the `7D 81` prefix and padding (§1.6). A row marked *RE only* is a
hypothesis until a recording shows it.

### 2.1 Outbound Host Request Commands
| Opcode | Name | Host Request (Hex) | Reply seen | Evidence | Description |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **0xA7 + 0xA2** | `UNLOCK_HANDSHAKE` | `7D 81 A7 80×6 7D 81 A2` (one write, §3.1) | `F0 70` | Vendor, CLI | Unlocks the MCU state machine |
| **0x9C [0x80]** | `SESSION_RESET` | `9C 80 00` | `F0 70` | CLI only | Resets the session iterator (the vendor tool never sends it) |
| **0x9C [0x01]** | `QUERY_SESSIONS` | `9C 01 1D` | `0xEC` | Vendor, CLI | Session header for slot 1 (§3.2) |
| **0x82** | `READ_RTC` | `82 02` | `0xF2` | Vendor, CLI | The reply is the same 8 bytes in every recording (§3.3) |
| **0x83** | `SET_RTC` | `83 YY MM DD HH MM SS 33 06 [chk]` | `F3 00 73` | Vendor | Sets the device clock (§3.3) |
| **0x9B [0x00]** | `DATA_STREAM_QUERY` | `9B 00 1B` (start) / `9B 7F 1A` (stop) | `0xEB` / `EB 7F 6A` | Vendor | Live stream (§3.4). The vendor tool also sends `9B 01 1C` right after a start; meaning unknown |
| **0x9D [0x02]** | `STORAGE_INIT` / `SEGMENT_ACK` | `9D 02 7F 7F 7F 00 00 1C` | none | Vendor, CLI | Sent before and after a download; no recording shows a reply (§3.5) |
| **0x9D [0x04 0x01]** | `READ_SPO2_BLOCK` | `9D 04 01 01 01 [off lo] [off hi] 00 [chk]` | `0xED` | Vendor, CLI | SpO2 series from a raw-sample offset (§3.5) |
| **0x9D [0x04 0x02]** | `READ_PULSE_BLOCK` | `9D 04 02 01 01 [off lo] [off hi] 00 [chk]` | `0xED` | Vendor, CLI | Pulse series from a raw-sample offset (§3.5) |
| **0x9D [0x7F]** | `DELETE_ALL` / `DELETE_ENTRY` | `9D 7F 7F 7F 7F 00 00 19` / `9D 7F 02 [user] [entry] 00 00 [chk]`, then `9D 7F 01 …` | `ED 7F … [status]` (§3.13) | Vendor | **Destructive** (decoded in T-037; §3.13). The vendor sent `DELETE_ALL` three times after the recorded download (its auto-delete). `fiedle400 clear` sends them since 0.4.29 |
| **0x81** | `QUERY_DEVICE_INFO` | `81 01` | `0xF1` | Vendor, CLI | Hardware model descriptor `"50F"` (§3.6) |
| **0xAD** | (device info, variant) | `AD` | `F0 70` | CLI | Bare ACK on this device (T7 note before §3.6) |
| **0x80** | `FIRMWARE_QUERY` | `80 00` | `F0 70` | Vendor, CLI | Bare ACK on this device; the documented `0xCF` reply is *RE only* (§3.7) |
| **0x8E** | `SERIAL_PROFILE_QUERY` | `8E 03 11`, `8E 06 14`, `8E 07 15` | `0xFE` | Vendor (03, 06, 07), CLI (03) | Profile string and two short replies (§3.8) |
| **0x9F** | `FLASH_GEOMETRY_QUERY` | `9F 1F` | `0xEF` | Vendor | Flash geometry; field meaning unverified (§3.9) |
| **0x8F** | (unknown) | `8F 04 00 13` | `FF 00 7F` | Vendor | Earlier drafts listed this as the geometry query; the device answers it with an `0xFF` frame |
| **0x9E** | (geometry, variant) | `9E 40 04` | `F0 70` | CLI | What `fiedle400 info` sends today; bare ACK |
| **0x90 [0x06]** | `USER_METADATA_QUERY` | `90 06 16` | `0xE0` | Vendor | 15-byte reply; the alarm-threshold field map is *RE only* (§3.11) |
| **0x94** | `FLASH_SECTOR_QUERY` | `94 14` | | *RE only* | Not in any recording (§3.10) |
| **0x9A** | (unknown) | `9A 1A` | not identified | Vendor | Last command of the vendor download; `analysis/bum400_20260906_100516.md` calls it "back to live mode" (unverified) |
| **0xA5** | `SESSION_SELECT` | `A5 [id] [chk]` | none | CLI (tested) | Serial-stream devices; this firmware does not answer (§3.12) |
| **0xA6** | `SESSION_DOWNLOAD` | `A6 [chk]` | none | CLI (tested) | Serial-stream devices; this firmware does not answer (§3.12) |
| **0xAA** | `FLASH_CLEAR` | `AA 00×6 [chk]` | | *RE only* | Never sent by `SpO2.exe` (§3.13) |
| **0x91..0x96** | (other data category) | `9N 00` / `9N 02` / `9N 7F` | `0xE1..0xE6` | *RE only* | Transfers for a data category this device does not report; not erase commands (§3.13) |

The Manual-mode commands (`0xA0`, `0xA3`, standalone `0xA2`, `0xA7 00/01`) are documented separately in §3.14.

### 2.2 Inbound Device Responses
| Response Header | Name | Frame length | Triggering Command | Evidence | Description |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **`0xF0`** | `COMMAND_ACK` | 2 B | handshake, `9C 80`, `0xAD`, `0x80`, `0x9E` | Vendor, CLI | `F0 70`. Also the reply to several queries the device does not support (T7 note before §3.6). |
| **`0xEC`** | `SESSION_INDEX` | 21 B | `9C 01` | Vendor, CLI | Session header: start date/time, 28-bit raw sample count, user name, checksum (§3.2). |
| **`0xED`** | `STORAGE_SUBFRAME` | 30 B (stream)* | `9D 04 [01/02]` | Vendor, CLI | Stored data: 14-bit sequence, 3 MSB masks (`m0..m2`), 21 data bytes, checksum (§3.5). |
| **`0xED 7F`** | (erase reply) | 7 B | `9D 7F …` | Vendor | `ED 7F [series] [user] [entry] [status] [chk]`, status 0 = done (§3.13). |
| **`0xEB`** | `LIVE_STREAM` | 6 B / 8 B / 3 B | `9B 00` | Vendor | Live stream; the three lengths and the field map are discussed in §3.4. |
| **`0xF2`** | `RTC_REPORT` | 8 B | `82 02` | Vendor, CLI | Same bytes in every recording, see §3.3. |
| **`0xF3`** | (set-clock reply) | 3 B | `83 …` | Vendor | `F3 00 73`. |
| **`0xF1`** | `DEVICE_INFO` | 10 B | `81 01` | Vendor, CLI | Hardware model descriptor ASCII string (`"50F     "`). |
| **`0xCF`** | `FIRMWARE_INFO` | 10 B | `80 00` | *RE only* | Never seen: this device answers `80 00` with `F0 70`. |
| **`0xFE`** | `PROFILE_INFO` | 10 / 7 / 5 B | `8E 03` / `8E 06` / `8E 07` | Vendor, CLI | Length depends on the sub-index (§3.8). |
| **`0xEF`** | `FLASH_GEOMETRY` | 8 B | `9F 1F` | Vendor | Flash geometry, field meaning unverified (§3.9). |
| **`0xFF`** | (unknown) | 3 B | `8F 04 00` | Vendor | `FF 00 7F`. |
| **`0xD4`** | `FLASH_SECTOR` | 18 B | `0x94` | *RE only* | Flash sector layout. |
| **`0xE0`** | `USER_METADATA` | 15 B | `90 06` | Vendor | Recorded reply does not fit the 7-byte alarm-threshold map (§3.11). |

\*) **Framing & Alignment**:
- Every reply is a frame of its own length that ends with its 7-bit checksum (§1.7). Most replies start at byte 0 of a 64-byte report and the rest is zero; several frames can share one report (in the vendor capture an `0xE0` reply and an `0xEB` frame arrive in the same report).
- **Continuous Stream (`0xED 0x04`)**: Stored session subframes are streamed continuously as unpadded 30-byte chunks across 64-byte USB HID report boundaries.

---

## 3. Byte Maps

### 3.1 UNLOCK_HANDSHAKE (`0xA7` + `0xA2`)

> [!NOTE]
> **Corrected 2026-10-15 against `fiedle400/protocol/commands.py`
> (`build_unlock_negotiate_handshake`) and verified live.** This is **one**
> 64-byte write, not two separate requests, and the unused tail is padded
> with `0x80`, not `0x00` -- a raw test using `0x00` padding and two
> separate writes got no response at all from the real device; this framing
> worked immediately. There is also no dedicated checksum byte for this
> command -- that is a correction to the earlier draft below, which stated
> checksums (`0x20`, `0x1B`) that do not match `sum(bytes[0..8]) % 128` for
> the literal key bytes shown (off by a consistent `+5`, i.e. internally
> inconsistent with its own stated formula) and do not appear in the real
> implementation at all.

#### Combined Request (one 64-byte write)
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Sync Prefix | `0x7D` | Protocol 0 sync marker |
| `0x01` | Channel ID | `0x81` | Target channel ID |
| `0x02` | Opcode | `0xA7` | Unlock Phase 1 |
| `0x03..0x08` | Key / Padding | `0x80` × 6 | Unlock key bytes |
| `0x09` | Sync Prefix | `0x7D` | Phase 2 begins immediately, no padding or checksum between phases |
| `0x0A` | Channel ID | `0x81` | |
| `0x0B` | Opcode | `0xA2` | Unlock Phase 2 / storage negotiation |
| `0x0C..0x3F` | Padding | `0x80` × 52 | Report padding |

#### Device Response: ACK (`0xF0`)
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xF0` | Acknowledge |
| `0x01` | Status | `0x70` | `0x70` = Success / MCU unlocked |
| `0x02..0x3F` | Padding | `0x00...` | Zero padding |

Confirmed by the vendor capture (`analysis/bum400_20260906_100516.pcap`): the device answers the
combined write with `F0 70`, as above. `fiedle400`'s own recordings of the identical write carry no
reply (the next command works either way); on the Linux `hid` backend the missing reply is part of
finding T8 (CHANGELOG.md).

---

### 3.2 SESSION_RESET & QUERY_SESSIONS (`0x9C`)

#### SESSION_RESET Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9C` | Session iterator control |
| `0x01` | Sub-command | `0x80` | `0x80` = Reset iterator to start |
| `0x02` | Checksum | `0x1C` | `(0x9C + 0x80) % 128 = 0x1C` |

On the wire this exists only as `fiedle400`'s own `7D 81 9C 80 00` (no checksum byte; the device
answers `F0 70`, `tests/fixtures/cli-exchange.trace.json`). The vendor tool never sends it, so the
checksum form above is unrecorded.

#### QUERY_SESSIONS Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9C` | Session query command |
| `0x01` | Next header | `0x01` | Always `0x01`. `SpO2.exe` sends `9C 01` from all three call sites (`0x4b8636`, `0x4b8d6a`, `0x4ba4c6`) and repeats it until a header with bit 6 set arrives; it is not a user selector (T-039) |
| `0x02` | Checksum | `0x1D` | `(0x9C + 0x01) % 128 = 0x1D` |

#### Device Response: Session Header (`0xEC`, 21 Bytes)
| Offset | Field | Format | Description |
| :--- | :--- | :--- | :--- |
| `0x00` | Header Opcode | `0xEC` | Session metadata packet identifier |
| `0x01` | Flags | Bitmask | Bit 6 (`0x40`): **last header**. While it is clear, `SpO2.exe` asks for the next one with `9C 01`; `fiedle400` stops on it too. Bits 0..3: `1` = the recording has a **third data series** (type `0x03`, probably perfusion index), which `SpO2.exe` then downloads after SpO2 and pulse; any other value = SpO2 and pulse only. `0` in all 11 recorded headers (T-066, below) |
| `0x02` | User | `uint8` | 1-based user number: `SpO2.exe` keeps one username and one list of entries per value, and sends it back as byte 3 of the `0x9D` page request. `fiedle400`'s `user_id`. Not a segment count (T-039) |
| `0x03` | Entry | `uint8` | 1-based entry (one recording) **within that user**; byte 4 of the `0x9D` page request. `fiedle400`'s `session_id`. The vendor captures show entries 1..4 for user 1; a second user has never been seen (§3.13, T-039) |
| `0x04` | Year | `uint8` | Years since 2000 (`26` = 2026) |
| `0x05` | Month | `1..12` | Month |
| `0x06` | Day | `1..31` | Day of month |
| `0x07` | Hour | `0..23` | Start hour |
| `0x08` | Minute | `0..59` | Start minute |
| `0x09` | Second | `0..59` | Start second |
| `0x0A..0x0D` | Raw Sample Count | 28-bit LE | `B0 \| (B1<<7) \| (B2<<14) \| (B3<<21)`. **Not seconds.** Counts raw 2 Hz half-second samples (confirmed: psytrap, 2026-10-15; previously mislabelled here as "1 Hz records", see CHANGELOG.md T3). `duration_sec = (raw_count + 1) // 2` (§1.4). |
| `0x0E..0x13` | Username | ASCII | `"user"` + `00 00` in every recording |
| `0x14` | Checksum | `0..127` | `sum(bytes[0..0x13]) % 128` (`0x42` in the vendor capture, `0x03` in the CLI recording) |
| `0x15..0x3F` | Padding | `0x00...` | Zero padding |

Corrected 2026-10-16 against both recordings: earlier drafts gave this as a 64-byte frame with a
16-byte username at `0x0E..0x1D`. The real frame is 21 bytes, matching §2.2:
`EC 40 01 01 1A 09 06 0A 00 2E 73 01 00 00 75 73 65 72 00 00 42` (vendor capture; 2026-09-06
10:00:46, 243 raw samples).

**User, entry and `fiedle400` session (T-039, from `SpO2.exe`; the vendor captures show entries 1..4 of user 1, §3.13).** The
`0xEC` reply handler is the case at `0x4ea405` of the reply parser (payload pointer
`[obj+0x124]`). It stores byte 1's low nibble at `+0x2f8`, bit 6 at `+0x2fc`, byte 2 at `+0x2f0`
and byte 3 at `+0x2f4` (getters `0x4c3c50`, `0x4c3c90`, `0x4c3c10`, `0x4c3c30`). The dialog that
lists recordings (`0x4b8807`-`0x4b8d9d`) then does the following:
- It grows its per-user tables to `byte2` entries and the entry list of user `byte2` to `byte3`.
- It stores the start time and sample count at `[byte2 - 1][byte3 - 1]`.
- It stores the username (bytes `0x0E..0x13`) once per `byte2`.
- It asks for the next header (`9C 01`) until bit 6 is set.

Downloads address a recording by both numbers. The `0x9D` page request carries `byte2` in its
byte 3 and `byte3` in its byte 4 (`0x4b8fd2`-`0x4b9059`; `fiedle400` builds the same bytes,
§3.5). So:
- a **user** is byte 2;
- an **entry** is byte 3, numbered per user;
- a `fiedle400` **session** is one entry, identified by both numbers.

**Byte 1, bits 0..3: third data series (T-066, static analysis plus every capture).** The
handler stores `byte1 & 0x0F`; the recording-list dialog (`0x4b8ce3`) sets its flag `+0x11c` to
`nibble == 1`, header by header, so the last header listed decides. With the flag set:
- buffers and progress count samples x 3 instead of x 2 (`0x4b7575`, `0x4b9329`, `0x4b98a2` and others);
- the download reads a third series with data type `0x03` (`9D 04 03 [user] [entry] lo hi`, §3.5),
  and Delete erases it as a third step (`9D 7F 03 [user] [entry]`, §3.13);
- the `0xED` parser hands type 3 to its own decoder (`0x4ec07a`): same subframe layout and deltas
  as SpO2 and pulse (27 samples), valid 1..220 (`0xDC`), stored times 10 as 16 bits, `0xFFFF`
  invalid.

What the series measures is not named in the code. The 0.1 steps up to 22.0 and the strings
`PI Graph Enabled` and `PI%` in `SpO2.exe` point to perfusion index in percent (inference).
The `0xEF` capability bytes can set the same flag on another path (§3.9). All 11 headers in
the captures (`bum400`, `bum400__2`, `bum400_download`, `raw/bum400_raw`, `realtime/bum400_realtime`)
have bits 0..3 = 0, and every `9D 04` asks for type 1 or 2. `fiedle400` ignores the nibble and
reads SpO2 and pulse, which stays correct for such a recording; it only leaves the third series out.

Still open: whether any PO-400 ever reports more than one user or entry. The "User 1..6" that
§3.13 once gave for `0x91`..`0x96` has no support (T-037).

Correction: `analysis/bum400_20260906_100516.md` §A.2 places this handler at `0x004c587a` with
fields `[this+0x1e8]`/`[this+0x1ec]` named "Total Segments" / "Segment Index". The binary does
not match: `0x4c587a` is unrelated code, and nothing reads those fields as a count. This table
used the doc's names until T-039.

---

### 3.3 READ_RTC (`0x82`) & SET_RTC (`0x83`)

#### READ_RTC Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x82` | Read clock |
| `0x01` | Checksum | `0x02` | `0x82 % 128 = 0x02` |

#### SET_RTC Request
| Offset | Field | Range | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x83` | Set clock |
| `0x01` | Year | `0..127` | Year since 2000 |
| `0x02` | Month | `1..12` | Month |
| `0x03` | Day | `1..31` | Day |
| `0x04` | Hour | `0..23` | Hour |
| `0x05` | Minute | `0..59` | Minute |
| `0x06` | Second | `0..59` | Second |
| `0x07` | Flags | `0x33` | Subsecond timing parameter |
| `0x08` | Reserved | `0x06` | Fixed parameter |
| `0x09` | Checksum | `0..127` | `sum(bytes[0..8]) % 128` |

#### Device Response: RTC Report (`0xF2`, 8 Bytes)
| Offset | Field | Range | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xF2` | RTC response identifier |
| `0x01` | Year | `0..127` | Year since 2000 (YY) |
| `0x02` | Month | `1..12` | Month |
| `0x03` | Day | `1..31` | Day |
| `0x04` | Hour | `0..23` | Hour |
| `0x05` | Minute | `0..59` | Minute |
| `0x06` | Second | `0..59` | Second |
| `0x07` | Checksum | `0..127` | `sum(bytes[0..6]) % 128` |

> [!WARNING]
> **The `0xF2` reply does not carry the current time on this device.** It is the same 8 bytes,
> `F2 00 00 02 07 00 0C 07`, in every recording: the vendor capture (2026-09-06, read before *and*
> after a `SET_RTC` that the device acknowledged with `F3 00 73`) and both CLI recordings
> (2026-10-15). With the field map above that would be year 0, month 0, which is no date at all.
> Up to 0.3.6, `fiedle400`'s parser read it from byte 3 instead, which turned the same bytes into
> 2002-07-01 12:07 (the minutes came from the checksum byte); `read-time` and `info` showed that
> date. Since 0.3.7 the reply is not decoded: `read-time` prints it raw and `info` says the clock
> is not reported. The stored session
> headers carry correct start times, so the device keeps time internally; it just does not report
> it here. The field map above is from the disassembly and unconfirmed.
>
> **This is most likely a bug or an unfinished feature in the device's own firmware, not a gap in
> `fiedle400`'s reverse-engineering.** The vendor's own `SpO2.exe` has the identical problem (that's
> where `F2 00 00 02 07 00 0C 07` was first captured from), and the reply never varies across two
> recordings made over a month apart, through a clock-set in between -- a working RTC readback
> would not do that. Treat "not reported" here as a statement about the hardware, not an invitation
> to look for a smarter way to decode these same eight bytes.
>
> The vendor's `SET_RTC` matches the table exactly (`83 1A 09 06 0A 05 18 33 06 0C`, checksum
> verified). `fiedle400 set-time` sends a different layout (`83 YY MM DD HH MI SS [chk] 01 34`,
> checksum `0x133 - sum`, `commands.build_set_time_command`) that is not in any recording, and
> `read-time` sends `82 02 00 00 00 00 00 84` where the vendor sends `82 02`.

---

### 3.4 DATA_STREAM_QUERY (`0x9B`) & Live Streaming (`0xEB`)

#### DATA_STREAM_QUERY Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9B` | Stream control |
| `0x01` | Control | `0x00` / `0x7F` | `0x00` = Start stream, `0x7F` = Stop stream |
| `0x02` | Checksum | `0x1B` / `0x1A` | `(0x9B + Control) % 128` |

#### Device Response: Live Sub-Frames (`0xEB`, 6 Bytes each)
Packed consecutively in 64-byte HID input reports:
| Offset | Field | Wire Range | Decoded Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | Sync Opcode | `0xEB` | — | Live frame identifier (`MSB=1`) |
| `0x01` | Status & Quality | `0x00..0x7F` | Bitfield | Bit 0: Finger-out (`1` = probe off, `0` = OK)<br>Bits 1..3: Signal bars (0..8)<br>Bit 4: Beat trigger (1 = pulse tick)<br>Bit 6: Pulse Rate MSB (Bit 7) *(Derived assumption based on CMS-50 UART protocol)* |
| `0x02` | Plethysmogram | `0x00..0x7F` | `0..127` | Real-time PPG waveform curve amplitude |
| `0x03` | Pulse Rate | `0x00..0x7F` | `0..254` | Pulse rate in BPM (`0xFF` = invalid); MSB is taken from `0x01` field (Bit 6) |
| `0x04` | SpO2 | `0x00..0x64` | `0..100` | Blood oxygen saturation % (`0x7F` = invalid / searching) |
| `0x05` | Checksum | `0x00..0x7F` | `0..127` | `sum(bytes[0..4]) % 128` |

> [!NOTE]
> **The only live-stream recording does not confirm this table.** The vendor capture (no finger
> on the probe) holds three `0xEB` frame shapes, each with a valid checksum at its own end:
> `EB 00 04 40 30 5F` (6 B, the bulk of the stream), `EB 01 06 7F 7F 7F 00 6F` (8 B, about every
> 20th report) and `EB 7F 6A` (3 B, the reply to `9B 7F 1A`). The length follows byte 1, so byte 1
> looks like a frame type rather than the status bitfield above. `fiedle400`'s live parser
> (`parsers.parse_hid_chunks`) already treats it that way (`0` = pleth, `1` = pulse and SpO2). A
> recording with a finger on the probe is needed before either reading is trusted. `fiedle400`
> stops the stream with `7D 81 9B 80 00`; the vendor tool uses `9B 7F 1A`.

---

### 3.5 Storage Transfer Commands (`0x9D`) & Subframes (`0xED`)

#### Storage Command Request (`0x9D`, 64 Bytes Outbound)

| Offset | Field | Value / Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9D` | Storage transfer command opcode |
| `0x01` | Mode | `0x02` / `0x04` | `0x02` = Init / ACK, `0x04` = Read block |
| `0x02` | Data Type | `0x01` / `0x02` / `0x03` / `0x7F` | `0x01` = SpO2 series, `0x02` = Pulse Rate, `0x03` = third series, only when `0xEC` byte 1 bits 0..3 = 1 (§3.2, T-066; never seen), `0x7F` = Init / ACK |
| `0x03` | User | `0x01` / `0x7F` | User number, byte 2 of the `0xEC` header (`0x7F` for Init / ACK; T-039) |
| `0x04` | Entry | `0x01` / `0x7F` | Entry within that user, byte 3 of the `0xEC` header (`0x7F` for Init / ACK; T-039) |
| `0x05` | Offset Low | `0x00..0x7F` | Sample offset (bits 0..6) -- **not** a block/page index, see note below |
| `0x06` | Offset High | `0x00..0x7F` | Sample offset (bits 7..13) |
| `0x07` | Reserved | `0x00` | Fixed zero |
| `0x08` | Checksum | `0..127` | `sum(bytes[0..7]) % 128` |
| `0x09..0x3F` | Padding | `0x00...` | Reserved zero padding |

#### Command Parameters
| Command | Mode `[0x01]` | Type `[0x02]` | User `[0x03]` | Entry `[0x04]` | Offset `[0x05..0x06]` | Checksum `[0x08]` | Description |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `STORAGE_INIT` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00 0x00` | `0x1C` *at `[0x07]`* | Sent before the download; no reply |
| `READ_SPO2_BLOCK` | `0x04` | `0x01` | `0x01` | `0x01` | offset | `0x24` at offset 0 | Reads SpO2 flash series |
| `READ_PULSE_BLOCK` | `0x04` | `0x02` | `0x01` | `0x01` | offset | `0x25` at offset 0 | Reads Pulse Rate flash series |
| `SEGMENT_ACK` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00 0x00` | `0x1C` *at `[0x07]`* | Same bytes as `STORAGE_INIT`, sent after the download; no reply |
| `DELETE_ALL` | `0x7F` | `0x7F` | `0x7F` | `0x7F` | `0x00 0x00` | `0x19` *at `[0x07]`* | **Destructive.** Erases every recording (§3.13). Vendor tool only, three times after the recorded download; reply not identified |
| `DELETE_ENTRY` | `0x7F` | `0x02`, then `0x01` (then `0x03`) | user | entry | `0x00 0x00` | `sum % 128` | **Destructive.** Erases one series of one recording; the vendor sends one per series, each after the device confirms the last (§3.13). Static analysis only |

The `0x02`/`0x7F` commands are **8 bytes** in the vendor capture (`9D 02 7F 7F 7F 00 00 1C`): no
reserved byte, checksum at `[0x07]`. `fiedle400` sends a 9-byte variant with the reserved `0x00`
(`9D 02 7F 7F 7F 00 00 00 1C`, `commands.build_session_data_command`). Neither gets a reply, and a
download works after both, so the difference has no visible effect so far.

> [!IMPORTANT]
> **The offset is a raw-sample sliding window, not a page index** (confirmed: psytrap, 2026-10-15,
> by exact byte comparison against a real device). Requesting offset `k` returns the session's data
> starting `k` *raw 2 Hz samples* in, not the k-th block of fresh data: `window(k)[i] == window(0)[i+k]`
> for every `i`, on both series. A client that requests offsets `0, 1, 2, ...` and concatenates the
> replies as if they were successive pages receives overlapping, re-shifted data, not new samples --
> this is exactly how `fiedle400`'s own download logic padded a 107-second (214-raw-sample, see §3.2)
> session out to 214 "records" before the bug was found (CHANGELOG.md T6). The correct read starts at
> offset 0 and, if a reply ends before the stored data does, continues at the offset where that reply
> ended; it never steps the offset 1, 2, 3, ... as if it were a page number.

> **Boundary probe (psytrap's laptop, 2026-10-15, `tests/fixtures/probe.trace.json`, one 214-sample session).**
> SpO2 reads at offsets 0, 1, 2, 50, 107, 150, 213, 214, 215, 300 show that every reply runs from the offset
> **to the end of the stored data** (214, 213, 212, 164, 107, 64 and 1 values; all equal to `window(0)[k:]`).
> At offset == stored samples (214) the device sends one frame of `0xFF` filler (`ED 04 01 00 00 7B 7F 7F ...`,
> which decodes to the `0xFF 0xFF` terminator, no samples); beyond it (215, 300) it sends **nothing**.
> `fiedle400` continues at offset `2 * records_so_far` and stops on a reply that adds no record (the end
> marker, or silence). That rule held on a real 937-record session that needed several replies (psytrap,
> 2026-10-15, CHANGELOG.md T6); how many samples one reply holds at most is not in any recording in this
> repository.
> **Mask bytes of a reply's last frame.** The bytes after the end of the data are padding that
> reassembles to `0xFF` (wire `0x7F` with its mask bit set), so the last frame's masks have a bit set for
> each padding byte; how many depends on where the data ends: `70 7F 7F` and `78 7F 7F` in the CLI recordings, `00 00 60` in the vendor capture. Either way
> `m2` is a mask byte, *not* a status flag (CHANGELOG.md T1).
> **Finger-out is not yet seen in any storage recording.** The `SpO2.exe` disassembly
> (`analysis/bum400_20260906_100516.md` §A.5) maps a *decoded* SpO2 outside 1..100 to `0x7F` (127) and a
> pulse outside 1..254 to `0xFF` (255) in its own records; those are the host's sentinels (they are also
> the `.SpO2` file's, §4), not proven wire values. `fiedle400` applies the same range check to the decoded
> values. What the device actually stores for a finger-out second is open (CHANGELOG.md T1,
> RELEASE_PLAN.md §3d).

#### Device Response: Stored Data Sub-Frame (`0xED`, 30 Bytes each)

| Offset | Field | Format | Description |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xED` | Storage subframe sync marker |
| `0x01` | Mode | `0x04` | Flash block transfer mode |
| `0x02` | Data Type | `0x01` / `0x02` | `0x01` = SpO2 series, `0x02` = Pulse Rate series |
| `0x03..0x04` | Sequence Index | 14-bit LE | `(Byte[4] << 7) \| Byte[3]` (0-based subframe counter) |
| `0x05..0x07` | Separated MSBs | 3 bytes | Bit 7 for compressed data bytes `0x08..0x1C` (7 bits each; Bit 7 unused) |
| `0x08..0x1C` | Compressed Data | 21 bytes | Lower 7 bits of data series (`& 0x7F`) |
| `0x1D` | Checksum | `0..127` | `sum(bytes[0..28]) % 128` |

#### MSB Reassembly (7-to-8 Bit Encoding)

All payload bytes transmitted over the wire are restricted to 7 bits (`MSB = 0`, range `0x00..0x7F`) to prevent collision with frame opcodes and sync markers (`MSB = 1`). Each 8-bit data byte is split during encoding:
* **Lower 7 Bits (`0x08..0x1C`)**: Masked with `0x7F` (`byte & 0x7F`) and transmitted as 21 payload bytes.
* **Separated MSBs (`0x05..0x07`)**: The MSB (Bit 7) of each byte is extracted and packed across 3 header bytes (7 MSBs per byte, Bits 0..6).

**Reassembly Process:**
The receiver restores each full 8-bit byte by recombining its lower 7 bits with its separated MSB:
$$\text{byte}[i] = (\text{MSB}_i \ll 7) \mid \text{payload}[i]$$

Each reassembled byte carries two delta nibbles (either SpO2 or Pulse Rate).

```python
# Reassemble 8-bit bytes from 7-bit payload and separated MSBs
msb_bytes = subframe[5:8]        # 3 bytes carrying 21 separated MSBs
data_bytes = subframe[8:29]      # 21 compressed data bytes (7-bit)

# Unpack 3 bytes into 21 individual MSB bits (7 bits each)
msb_bits = [(byte >> bit) & 1 for byte in msb_bytes for bit in range(7)]

reassembled = bytearray()
for msb, byte in zip(msb_bits, data_bytes):
    reassembled.append((msb << 7) | byte)
```

#### Delta-Nibble Decompression
1. **Dynamic Baseline Initialization (`0xF_ 0xF_` Escape)**:
   - The current `Base` acts as the **local upper envelope (maximum)** for subsequent samples.
   - When a byte has high nibble `0xF_`, it pairs with the next `0xF_` byte to establish an 8-bit dynamic baseline:
     $$\text{Base} = ((B_1 \ \& \ 0\text{x}0\text{F}) \ll 4) \mid (B_2 \ \& \ 0\text{x}0\text{F})$$
     *(e.g., `0xF6 0xF2` $\implies \text{Base}_{\text{SpO2}} = 98\%$; `0xF3 0xFA` $\implies \text{Base}_{\text{HR}} = 58\text{ BPM}$)*
   - **Encoder Trigger Conditions**: The encoder emits a new baseline escape whenever:
     - The measured value exceeds the current baseline ($\text{Value} > \text{Base}$).
     - The measured value drops by more than 14 points below the baseline ($\text{Base} - \text{Value} > 14$).
   - **Cross-Subframe Split Base**: If $B_1$ occurs at byte index 28 (end of subframe), $B_2$ is read from index 8 of the next subframe.
2. **Stream Terminator**: `0xFF 0xFF` indicates the end of recorded flash data.
3. **Delta-Nibble Extraction (2 Hz Half-Second Samples)**:
   - Each byte carries two unsigned 4-bit nibbles (`0x0..0xE`, 0..14) subtracted from `Base`:
     $$\text{Sample}_1 = \text{Base} - (B \gg 4)$$
     $$\text{Sample}_2 = \text{Base} - (B \ \& \ 0\text{x}0\text{F}) \quad (\text{skipped if nibble is } 0\text{x}0\text{F} \text{ padding})$$
   - **Ceiling Bound**: Because nibbles are unsigned subtractions, $\text{Sample}_{\max} = \text{Base} - 0 = \text{Base}$. Samples can never exceed the baseline using deltas.
   - **Zero Delta**: $B = 0\text{x}00$ represents $\Delta = 0$ ($\text{Sample} = \text{Base}$). Zero bytes are valid data and must **not** be dropped.
   - **Two raw samples become one physiological value**: `Sample_1` and `Sample_2` are genuinely
     independent half-second readings, not a repeated/duplicated value -- the device takes two raw
     measurements per second, and the firmware's record (and this decoder, matching it) averages them
     into a single 1 Hz sample: `round((Sample_1 + Sample_2) / 2)`. This is confirmed physiology/firmware
     behaviour (psytrap, 2026-10-15), not a decode approximation. It is why the session header's raw
     sample count (field `0x0A..0x0D` in §3.2) is exactly double the real recording duration and the
     real 1 Hz record count.
4. **End-of-Data Sentinel**: A subframe with `mode = 0x00`, `seq = 0`, and masks containing `0x7F` indicates an uninitialized flash segment and signals immediate termination (from the disassembly; not in any recording). The end marker that *is* recorded looks different: a read at offset == stored samples returns `ED 04 01 00 00 7B 7F 7F 7F 7F 0F 7F ...` (mode `0x04`, seq 0), whose first two data bytes reassemble to the `0xFF 0xFF` terminator (`tests/fixtures/probe.trace.json`).

---

> [!IMPORTANT]
> **A query below can be answered with a bare `COMMAND_ACK` (`0xF0 0x70`, see §2.2) instead of its
> documented response** (confirmed: psytrap, 2026-10-15, on a real device for the `0xAD` and `9E 40 04`
> variants of these queries, CHANGELOG.md T7; `80 00` likewise, in the vendor capture and
> `tests/fixtures/probe.trace.json`). This is not a framing error -- it is a valid,
> differently-shaped reply, and a client must check the response's own opcode byte before parsing it as
> the expected structure. Code that assumes the documented opcode and blindly parses whatever arrives
> will misread the ACK's status byte as field data, or pick up an unrelated response left over from a
> different query (on the affected device, this is how the model string from §3.6 ended up printed as a
> serial number, and the ACK's `0x70` status byte as a flash geometry value). The safe fallback when the
> response opcode does not match is "not reported", never a value synthesised from the wrong bytes.

### 3.6 QUERY_DEVICE_INFO (`0x81` / `0xAD`)

#### Request (`0x81`)
`[0x81, 0x01]` (Checksum: `0x01`). `0xAD`, listed with it in earlier drafts, gets only `F0 70`.

#### Device Response (`0xF1`, 10 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xF1` | Device info header |
| `0x01..0x08` | Model String | ASCII | `"50F     "` (CMS50F / PO-400) |
| `0x09` | Checksum | `0x3C` | `sum(bytes[0..8]) % 128` |

---

### 3.7 FIRMWARE_QUERY (`0x80`)

#### Request (`0x80`)
`[0x80, 0x00]` (Checksum: `0x00`)

#### Device Response (`0xCF`, 10 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xCF` | Firmware info header |
| `0x01..0x08` | Version String | ASCII | `"V3.1    "` |
| `0x09` | Checksum | `0..127` | `sum(bytes[0..8]) % 128` |

**Never observed.** This device answers `80 00` with a bare `F0 70`, three times in the vendor capture
and once in `tests/fixtures/probe.trace.json`, so it reports no firmware version over this
protocol. The `0xCF` map and the `"V3.1"` example come from the disassembly only.

---

### 3.8 SERIAL_PROFILE_QUERY (`0x8E`)

#### Request (`0x8E`)
| Sub-Index | Request Bytes | Description |
| :---: | :--- | :--- |
| `0x03` | `8E 03 11` | Username query |
| `0x06` | `8E 06 14` | Profile query |
| `0x07` | `8E 07 15` | Serial number query |

#### Device Response (`0xFE`)
The length depends on the sub-index. Recorded replies (vendor capture; `03` also in the CLI recordings):

| Request | Reply | Length | Content |
| :--- | :--- | :---: | :--- |
| `8E 03 11` | `FE 03 20 20 20 75 73 65 72 20` | 10 B | Sub-index echo, 7-character text `"   user"`, checksum `0x20` at `0x09` |
| `8E 06 14` | `FE 06 07 00 00 00 0B` | 7 B | Sub-index echo, `07 00 00 00`, checksum; meaning unknown |
| `8E 07 15` | `FE 07 00 00 05` | 5 B | Sub-index echo, `00 00`, checksum: **no serial number text** on this device |

Earlier drafts gave one 11-byte layout with an 8-character string at `0x02..0x09` and the checksum at
`0x0A`; no recorded reply has that shape. The vendor tool sends all three before it downloads, and the
session it then downloads is intact, so these are queries, not erase commands (compare the different
claim in `analysis/bum400_20260906_100516.md` §A.6, which is unverified).

---

### 3.9 FLASH_GEOMETRY_QUERY (`0x9F`)

#### Request (`0x9F`)
`[0x9F, 0x1F]` (Checksum: `0x1F`). This is the request the vendor tool sends (three times) and the one
the `0xEF` reply follows. Earlier drafts gave `[0x8F, 0x04, 0x00, 0x13]` here; the vendor sends that too,
but the device answers it with `FF 00 7F`, not `0xEF`. `fiedle400 info` sends `9E 40 04`, which gets
`F0 70`.

#### Device Response (`0xEF`, 8 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xEF` | Flash geometry header |
| `0x01` | Sector Count | `uint8` | Number of flash sectors |
| `0x02..0x03` | Block Size | 14-bit LE | Block size in bytes (64 or 256) |
| `0x04..0x06` | Capacity | 21-bit LE | Total capacity |
| `0x07` | Checksum | `0..127` | `sum(bytes[0..6]) % 128` |

The only recorded reply is `EF 00 01 40 00 00 00 30`. Read with this map it gives 0 sectors, a block
size of `0x01 | 0x40 << 7` = 8193 and zero capacity, which fits neither 64 nor 256; the field meanings
are unconfirmed.

**What `SpO2.exe` does with it (T-037, static analysis).** The reply parser copies bytes `0x03..0x06`
into one 4-byte field (`0x4eaba5`). It also sets a flag when byte `0x02` is non-zero. The download
dialog reads the first of those bytes as a bitmask of the kinds of stored data, and picks a
download path from it (`0x4b0d27`-`0x4b0f30`, `0x4ba6c7`):
- `0x40`: Auto-mode recordings. It sends `90 06`, then the `0x9C`/`0x9D` download.
- `0x01`: another kind. It sends `90 00` or `90 01`, then the `0x91`..`0x96` transfers (§3.13).
- `0x10`: a third kind. It sends `90 04`.

The recorded `40` matches what the vendor then sent (`90 06`, then `9C`/`9D`). So these bytes are a
capability mask, not flash geometry; the name of this section is historical.

In the download dialog (`0x4ba6c7`), when the first copied byte has neither `0x40` nor `0x01` but
the third has bits 0 and 1 set, that third byte's bit 4 (`0x10`) sets the same third-series flag
as `0xEC` byte 1 (§3.2, T-066). The recorded reply never takes that path.

---

### 3.10 FLASH_SECTOR_QUERY (`0x94`)

#### Request (`0x94`)
`[0x94, 0x14]` (Checksum: `0x14`). Not in any recording; this section is from the disassembly only.

#### Device Response (`0xD4`, 18 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xD4` | Sector layout header |
| `0x01` | Total Blocks | `uint8` | Flash blocks count |
| `0x02..0x03` | Block Pages | 14-bit LE | Pages per block |
| `0x04..0x10` | Sector Map | Bytes | Sector allocation bitmask |
| `0x11` | Checksum | `0..127` | `sum(bytes[0..16]) % 128` |

---

### 3.11 USER_METADATA_QUERY (`0x90`)

#### Request (`0x90`)
`[0x90, 0x06, 0x16]` (Checksum: `0x16`)

#### Device Response (`0xE0`, 7 Bytes)
| Offset | Field | Range | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xE0` | Alarm metadata header |
| `0x01` | Sub-Index Echo | `0x06` | Echo of requested index |
| `0x02` | SpO2 Low Limit | `0..100 %` | Lower SpO2 alarm limit |
| `0x03` | SpO2 High Limit | `0..100 %` | Upper SpO2 alarm limit |
| `0x04` | PR Low Limit | `25..250 BPM` | Lower Pulse Rate alarm limit |
| `0x05` | PR High Limit | `25..250 BPM` | Upper Pulse Rate alarm limit |
| `0x06` | Checksum | `0..127` | `sum(bytes[0..5]) % 128` |

The recorded reply (vendor capture) is 15 bytes, checksum at `0x0E`:
`E0 06 01 00 01 00 00 52 1F 00 1A 4E 1F 00 60`. Bytes `0x02..0x05` (`01 00 01 00`) are not plausible
alarm limits, so the map above is unconfirmed.

---

### 3.12 SESSION_SELECT (`0xA5`) & SESSION_DOWNLOAD (`0xA6`)

Used on serial-stream device models:
- **Select Session**: `[0x7D, 0x81, 0xA5, session_id, chk]`
- **Start Download**: `[0x7D, 0x81, 0xA6, 0x00, chk]`
- **Response**: Device returns `0xF0 0x70` ACK or begins streaming `0xEB` frames.

Tested on this (flash-storage) PO-400 for session ids 1-3: neither command gets any reply, not even an
ACK (CHANGELOG.md, "Manual-mode protocol"). Serial-stream devices are untested.

---

### 3.13 Deleting recordings (`0x9D 7F`; not `0xAA` or `0x91`..`0x96`)

> [!CAUTION]
> **Destructive Operations**:
> - `9D 7F 7F 7F 7F 00 00 19` erases every recording, and `9D 7F 02 [user] [entry]` erases one
>   (decoded from `SpO2.exe`, T-037). No automated test may send either to a real device.
> - `0xAA` and `0x91`..`0x96`, listed here in earlier drafts, are not erase commands for this
>   device (see below).

**Decoded in T-037 (static analysis of `SpO2.exe`, then checked against every vendor capture).** The
erase commands for this device are `0x9D` commands with mode `0x7F`, not `0xAA` or `0x91`..`0x96`.
The vendor's "Device Stored Data" dialog (resource 148) has four buttons: Receive, Delete,
Delete User and Delete All.

| What | Bytes | Where in `SpO2.exe` |
| :--- | :--- | :--- |
| Delete All, and the automatic delete after saving | `9D 7F 7F 7F 7F 00 00 19` | `0x4af695`. Called by the Delete All button (`0x453`, `0x4a3e76`) and, after a download, when the setting `bAutoDeleteSegmentSaveData` is unset or non-zero (`0x4a48fc`-`0x4a494b`). Only in Auto mode (category `0x40`, §3.9). **Confirmed against a real device (2026-10-21, T-074):** `ED 7F` status 0, both sessions actually gone afterwards |
| Delete (the selected recordings) | `9D 7F 02 [user] [entry] 00 00 [chk]` (pulse series), then `9D 7F 01 …` (SpO2), then `9D 7F 03 …` if the recording has a third series (§3.2). **Tried against a real device (2026-10-21, T-074): does not erase anything.** The device answers with a plain `F0 70` ack (not `ED 7F`), and the session is unchanged afterwards -- unlike Delete All below, this byte layout is static analysis only and has never been seen on the wire | `0x4af43c`, Delete button (`0x3e8`, `0x4a3ddd`), sends the first. The reply handler sends the next one when the device confirms the last (`0x4b9e19`-`0x4ba07d`, T-066). `user`/`entry` as in the `0xEC` header (§3.2) |
| Delete User | no command for this device | `0x4af5ef` sends `A1 00`, or `0xAE` in a `7D 80` frame, on other device types, and nothing on the `0x9C`/`0x9D` path |
| Delete for the `0x91`..`0x96` data category | `91 7F` | `0x4af547` |
| Delete on the Manual-mode path | `A1 00 21`, then `A1 01 22`, then `A1 04 25` if the third-series flag is set, each after a `D1` reply | §3.14 G (T-072) |

**Confirmed by the vendor captures.** Every vendor capture that downloads also ends with the
automatic delete-all, after the last `9D 04` page request. (`fiedle400` deliberately does not:
`download` never erases, and erasing is always a step the user confirms; T-038.)

| Capture (`archive/capture/`, `analysis/`) | Date | Headers (user, entry: start) | Ends with `9D 7F 7F 7F 7F` |
| :--- | :--- | :--- | :--- |
| `bum400.pcapng` | 09-03 07:29 | 1,1: 09-02 22:32; 1,2: 09-03 01:14 | yes, after downloading both |
| `bum400__2.pcapng` | 09-03 ~08:59 | 1,1: 09-03 08:12 | no (no download) |
| `bum400_download.pcapng` | 09-05 09:46 | 1,1: 09-03 08:12; 1,2..1,4: 09-04 21:46 .. 09-05 00:28 | yes, after downloading all four |
| `raw/bum400_raw.pcapng` | 09-05 15:59 | 1,1: 09-05 09:53; 1,2: 13:11; 1,3: 13:17 | yes |
| `realtime/bum400_realtime.pcapng` | 09-05 18:13 | 1,1: 09-05 16:11 | yes |
| `bum400_20260906_100516.pcap` | 09-06 10:05 | 1,1: 09-06 10:00 | yes, sent three times |

Every capture after an erase starts again at entry 1 with only newer recordings, and the one
capture without an erase (`bum400__2`) left its recording in place for the next. So
`9D 7F 7F 7F 7F 00 00 19` erases every recording, and the device renumbers from 1.

**Erase reply (T-066).** The device confirms an erase with `ED 7F [series] [user] [entry] [status]
[chk]`, 7 bytes; status `0` = done. `bum400.pcapng` and `raw/bum400_raw.pcapng` show
`ED 7F 7F 7F 7F 00 69` right after the delete-all (behind an `EF 00 00 00 00 00 00 6F` frame in
the same report). `SpO2.exe` parses it at `0x4ea813` (bytes 2..4 kept, byte 5 == 0 as "OK"):
- after delete-all with status 0 it clears its tables;
- after delete-one it sends the next series' delete, and reports an error on a non-zero status.

No capture
contains `9D 7F 02` (delete one), `0xAA`, `0xAB`, `0xAC`, `0xAF` or `0x91`..`0x96`.

Notes on the other candidates:
- **`0xAA` and `0x91`..`0x96` are not erase commands for this device.** `SpO2.exe` never sends
  `0xAA`: none of its 137 send sites uses it. `0x91`..`0x96` are a transfer family for a different
  kind of stored data (the `0x01` category of §3.9):
  - the device answers them with `0xE1`..`0xE6` (reply handler cases `0x4ba821`-`0x4bb4d0`);
  - the program follows up with `9N 02` to continue and `9N 7F` to finish, appending the items in
    blocks of ten;
  - the program's Bluetooth path sends some of the same opcodes (`0x4bf109`-`0x4bf463`) before it
    stores spot-check SpO2 and step-counter records (`insert spo2Single`, `insert step`).

  §A.6's "user erase after every download" reading is wrong, and "User 1..6" has no support.
- **`fiedle400 clear`** (`engine/device.py`, since 0.4.29) sends the vendor's commands: after
  listing the recordings and `9D 02`, `9D 7F 7F 7F 7F 00 00 19` for all, or for one
  `9D 7F 02 [user] [entry] ...` and then `9D 7F 01 …`, like the vendor (since 0.4.38; 0.4.29 to
  0.4.37 sent only the first, T-066). It stops if an erase reply has a non-zero status. Then it
  lists them again and reports whether they are gone. Up to 0.4.28 it
  sent `0xAF`, `0xAB`, `0xAA`, `0xAC`, none of which the vendor sends (T-037).
- Switching the device between Auto and Manual recording mode on the device itself erases its memory
  (CHANGELOG.md, "Manual-mode protocol").

---

### 3.14 Manual Recording Protocol (`0xA0`/`0xD0`, `0xA2`/`0xD2`, `0xA3`/`0xD3`, `0xA7`/`0xD8`)

> [!IMPORTANT]
> **Implemented in T-042** (`fiedle400/protocol/manual.py`, `SerialDeviceEngine.download_manual`):
> `sessions`, `download` and the wizard list and read the Manual-mode recording when the Auto
> list is empty. Found 2026-10-15 via a live USB capture of the vendor's own SpO2 Assistant
> reading a **Manual-mode** recording. The layouts below were checked on 2026-10-21 against
> `SpO2.exe`: header parser `0x4e92ac`, SpO2 subframe decoder `0x4e9440`, pulse `0x4e97ce`,
> download dialog cases `0x4b6c46` (`D0`) and `0x4b75c6` (`D3`). (The `0x004c4875` cited here
> before is an unrelated list helper.) This is a **separate, parallel**
> protocol from the `0x9C`/`0x9D` flash-index commands used everywhere else
> in this document, which only ever read **Auto-mode** sessions -- that is
> the root cause of the Manual-mode session visibility question in
> `RELEASE_PLAN.md` §3d: Manual-mode data was never reachable via `0x9C`/
> `0x9D` at all, by design, not by a bug or a missing argument.
>
> **Opcode `0xA2` is reused.** §3.1's `UNLOCK_HANDSHAKE` already sends `0xA2`
> as the second half of a combined `0xA7`-then-`0xA2` preamble. The request
> below is a standalone, single-opcode `A2 00 00 00 22` with a completely
> different meaning (pulse-rate data). Disambiguate by context -- whether it
> immediately follows an `0xA7` phase-1 write, or stands alone -- not by the
> opcode byte in isolation.

#### A. Manual Recording Header (`0xA0` -> `0xD0`)

Request: `A0 00 20` (sub-command `0x00`, checksum `0x20`).

| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xD0` | Manual recording header response |
| `0x01` | Kind | `0x00` in the capture | `SpO2.exe` maps `0`, `1` and `4` to an internal type; `fiedle400` decodes every kind like `0` |
| `0x02..0x04` | Date | `YY MM DD` | e.g. `1A 0A 0F` = 2026-10-15 (`0x1A` = 26 -> `2000+26`) |
| `0x05..0x07` | Time | `HH MM SS` | e.g. `13 22 10` = 19:34:16 |
| `0x08..0x09` | Unknown | `00 00` in the capture | Not read by `SpO2.exe`'s header parser |
| `0x0A..0x0C` | Sample count | 21-bit, 7-bit little-endian: `b0 \| b1<<7 \| b2<<14` | `3B 00 00` = 59. One sample per second (§F); `SpO2.exe` reads exactly this many samples per series. (Earlier drafts read `00 00 3B` at `0x08..0x0A` as a big-endian "duration", which gives the same 59 here only by chance) |
| `0x0D` | Checksum | `0..127` | `sum(bytes[0x00..0x0C]) % 128` (`0x03` in the capture). The frame is 14 bytes; the rest of the report carries live-stream frames (`EB ...`) |

#### B. SpO2 Data Block (`0xA3` -> `0xD3`)

Request: `A3 00 lo hi chk`: start at subframe `lo | hi << 7` (`A3 00 00 00 23` = from the
start). `SpO2.exe` asks once; the device then sends every subframe, three per report, until the
series is complete. When a subframe number is not the next one expected, `SpO2.exe` sends
`A3 7F 00 00 22` and asks again from the missing subframe (`0x4b75c6`); `fiedle400` does the
same, up to three times.

Response: one 64-byte report holds **three** 20-byte subframes back to back,
plus 4 bytes of trailing padding:

| Byte range | Content |
| :--- | :--- |
| `0x00..0x13` | Subframe 0: `D3 00 00` + 16 data bytes + checksum |
| `0x14..0x27` | Subframe 1: `D3 01 00` + 16 data bytes + checksum |
| `0x28..0x3B` | Subframe 2: `D3 02 00` + 16 data bytes + checksum |
| `0x3C..0x3F` | Padding, `00 00 00 00` |

#### C. Pulse Data Block (`0xA2` -> `0xD2`)

Request: `A2 00 00 00 22` (start at subframe 0). Identical 64-byte, three-
subframe layout to `0xD3` above, opcode `0xD2` in place of `0xD3`.

#### D. Block Acknowledgment (`0xA7` -> `0xD8`)

| Series | Request | Response |
| :--- | :--- | :--- |
| SpO2 | `A7 01 28` | `D8 01 00 59` |
| Pulse | `A7 00 27` | `D8 00 00 58` |

**`0xD8` response fields** (from the `SpO2.exe` disassembly @ `0x004c55ba`):

| Offset | Field | Notes |
| :--- | :--- | :--- |
| `0x00` | Opcode | `0xD8` |
| `0x01` | Block type | `0x01` = SpO2, `0x00` = Pulse |
| `0x02` | Status | `0x00` = success (code checks `== 0`, sets an internal ACK flag) |
| `0x03` | Checksum | `0x59` (SpO2) / `0x58` (Pulse) |

**Internal module identification** (string cross-references in the same
disassembly): MFC name `STR_StorageManual` / "Single Spo2"; database table
`Spo2Single` (`.?AVCDbSpo2SingleInfo@@`); export path
`%s\50KReview\Spo2Single\*.csv`. Confirms "Manual" and "Single SpO2" are the
vendor's own names for this recording mode and its storage path.

#### E. End of Manual Download

`A3 7F` (SpO2) and `A2 7F` (Pulse) signal the regular end of the manual
download to the device -- the same role `0x9D 0x02` (`SEGMENT_ACK`, §3.5)
plays for the Auto-mode storage path.

**Typical exchange, in plain terms** (relayed description, not re-verified
line by line, but consistent with everything confirmed above):

1. **Query the header.** Host: "Do you have a manually saved single
   recording in storage?" Device: "Yes -- a recording from the stated date
   and time, N seconds long."
2. **Fetch SpO2.** Host: "Send me the oxygen values for that recording."
   Device streams the `0xD3` subframes (base value plus compressed
   follow-on deltas). Host ACKs each block; device confirms SpO2 transfer
   complete.
3. **Fetch Pulse.** Same exchange with `0xD2`.
4. **End download, resume live mode.** Host: "I have everything, end the
   download." Device resumes its normal continuous live stream (pulse,
   SpO2, waveform) for the on-device display.

#### F. Delta-Nibble Decompression (`0xD3` / `0xD2` payload)

**As `SpO2.exe` decodes it** (`0x4e9440` SpO2, `0x4e97ce` pulse; corrected 2026-10-21, T-042).
Every subframe stands for exactly **27 samples, one per second**, and the series is read until
the header's sample count is reached (the last subframe is cut there).

| Record offset | Field | Meaning |
| :--- | :--- | :--- |
| `0x01..0x02` | Subframe number | `b1 \| b2 << 7` |
| `0x03..0x04` | Unknown | Not read by the decoder |
| `0x05` | **First value** | SpO2 in % (valid 1..100), pulse in bpm (valid 1..254). An SpO2 outside that range is `0x7F` and makes the whole subframe "no finger" |
| `0x06..0x12` | Deltas | 13 bytes, two deltas each, high nibble first: 26 more samples |
| `0x13` | Checksum | `sum(bytes[0x00..0x12]) % 128` |

Each nibble is sign (bit 3) and magnitude (bits 0..2), added to the previous sample. There is
**no terminator**: the nibble `0xF` (negative 7) marks an invalid sample (`0x7F` SpO2, `0xFF`
pulse), and the deltas after it build on that invalid value, so the rest of the subframe stays
invalid (`0x7F` filler bytes after the end of a recording do exactly that). After decoding,
any SpO2 outside 1..100 and any pulse outside 1..254 is invalid.

The pulse decoder accepts a first value of `0x7F` (127 bpm), so the all-`0x7F` subframes decode
to noise for pulse (127, 134, invalid, 6, ...: `0xFF + 7` wraps to 6). `fiedle400` therefore
keeps a pulse value only where the SpO2 sample of the same second is valid.

**Reference capture: `archive/capture/bum400_20261015_194301.pcap`** (psytrap, 2026-10-15
19:43, SpO2 Assistant downloading one manual recording; added to the archive 2026-10-21, not in
git). The whole exchange, after the `8F 04` / `9A` traffic of the open dialog:

```
OUT A0 00 20                 IN D0 00 1A 0A 0F 13 22 10 00 00 3B 00 00 03   2026-10-15 19:34:16, 59 s
OUT 80                       (stop live stream)
OUT A3 00 00 00 23           IN D3 x3 subframes (below)
OUT A7 01 28                 IN D8 01 00 59
OUT A2 00 00 00 22           IN D2 x3 subframes (below)
OUT A7 00 27                 IN D8 00 00 58
OUT A3 7F 00 00 22
OUT A2 7F 00 00 21           (end; no erase of any kind is sent)
OUT 9B 00 1B, 9B 01 1C       (live stream back on)
```

The host asks once per series, and one reply holds the whole recording. Every subframe checksum
is correct:

| seq | SpO2 (`D3`) | Pulse (`D2`) | bytes 3, 4 (SpO2 / Pulse) |
| :--- | :--- | :--- | :--- |
| 0 | no finger (all `7F`) | no finger | `7F 7F` / `7F 7F` |
| 1 | 96 x5, then 97 x9 (14 samples) | 57, 63, 69, then 71 x11 (14 samples) | `08 7E` / `04 7E` |
| 2 | no finger | no finger | `7F 7F` / `7F 7F` |

Decoded as `SpO2.exe` does (§F), that is 59 one-second samples: 27 without a finger
(19:34:16-19:34:42), 14 with SpO2 and pulse (19:34:43-19:34:56), and 18 without a finger to the
end. "One per second" rests on the header count being named a duration and on `SpO2.exe`
reading exactly that many samples; a stopwatch-timed recording would confirm it.

> [!WARNING]
> **Corrected 2026-10-21 against the capture above.** Earlier drafts gave a "decoded reference
> capture" with 7 subframes per series (SpO2 96-100%, Pulse 62-67, 59 samples with signal over
> ~140), and quoted byte 4 as `0x7C, 0x00, 0x7F, 0x7F` / `0x7D, 0x00, 0x7F, 0x7F`. None of that
> is in the only capture there is, which has the same header (19:34:16, 59 s). Where those values
> came from is unknown. Byte 3 of the one
> data subframe is `08` for SpO2 and `04` for Pulse, which is what the "channel marker" reading in
> (a) predicted. The framing question from the docs review (M1) is settled: one 64-byte report
> holds three 20-byte subframes and 4 padding bytes. The header example (M2) is this recording.

> [!NOTE]
> **Superseded notes (2026-10-15).** Earlier versions of this section carried notes on the
> wrong base offset (`0x03` instead of `0x05`), on bytes 3..4, on nibble order, on "41 s of real
> data in a 59-sample stream" and on `0x7F` padding. The decoder in §F settles them: the base is
> at `0x05`, bytes 3..4 are not read, high nibble first, and the 41 s are the 27 no-finger plus
> 14 measured seconds of the capture above. See git history for the old text.

**2026-10-21, second capture: a 5-minute, 315-sample manual recording** (psytrap, real
hardware, `fiedle400` CLI `download`, not SpO2 Assistant). One deliberate finger-out partway
through. Resolves the "one per second" timing question and tests the bytes-3..4 hypothesis
above against more than one data point:

- **Timing confirmed.** All 315 downloaded records carry the device's own RTC timestamp,
  incrementing by exactly one second with no gaps or repeats across the whole recording
  (`15:48:16` to `15:53:30`). The `0xD0` header's 21-bit sample count (315) matches the
  downloaded record count and the first timestamp exactly. This settles "one sample per
  second" without needing an independently-timed stopwatch: the device's own clock already
  shows uniform 1 Hz spacing for 315 consecutive samples.
- **Bytes 3..4 hypothesis from the single-sample capture above does not hold.** That capture
  (one `7F 7F` no-finger subframe, one `08 7E`/`04 7E` finger-on subframe) suggested these
  bytes mark finger-on/off per subframe. Across this recording's 12 subframes, bytes 3..4
  vary subframe-to-subframe (`20 00`, `10 00`, `40 00`, `20 02`, `00 08`, `00 20`, `02 20`,
  `00 00`, `02 00`, `40 00`, `02 7a`, SpO2 side) even though every sample in those subframes
  has the finger on -- so this is not a simple per-subframe finger-status flag. The one
  subframe spanning the finger-out transition (subframe 9, valid samples followed by invalid
  ones) comes closest to the old `7F 7F` pattern at `70 7F`, but isn't an exact match either.
  Still unknown; likely some kind of running counter or checksum rather than a status marker.
- **`D0` kind byte:** still `0x00` in this capture too; kinds `1` and `4` remain unobserved,
  with no known way to trigger them.

#### G. Erase (`0xA1` -> `0xD1`) -- confirmed against real hardware (T-072/T-073)

`SpO2.exe` has an erase for this path, reverse-engineered by static analysis and never captured
on the wire. `fiedle400` sends steps 1 and 2 (`clear`, 0.4.40+); as of 2026-10-21 this has been
run against a real device holding a real Manual-mode recording, got a status-0 `D1` reply for
each step, and the recording was actually gone afterwards (`fiedle400 sessions` -- "No stored
recording sessions found", not just unlisted). The byte layout below is now confirmed to erase;
whether it is byte-for-byte what the vendor app itself sends is still open (no packet capture of
SpO2.exe's own Delete exists -- T-073).

| Step | Host | Device reply |
| :--- | :--- | :--- |
| 1 | `A1 00 21` | `D1 00 [status] [chk]` |
| 2, after status 0 | `A1 01 22` | `D1 01 [status] [chk]` |
| 3, after status 0, only with the third-series flag (§3.2) | `A1 04 25` | `D1 04 [status] [chk]` |

- **Reply:** the `0xD1` parser (`0x4ea145`) keeps byte 1 and treats byte 2 == 0 as done. The
  dialog's `0xD1` case (`0x4b6f58`-`0x4b710d`) sends the next step, or shows the result message
  (`0xAE`: 0 = done, 4 = failed). The byte-1 values 0, 1 and 4 are the same set as the `D0` kind
  byte; whether they name series or kinds is not decoded.
- **What sends step 1:**
  - The Delete button (`0x4af562`), when the device did not report the `0x40`/`0x01` categories
    (`0xEF`, §3.9); otherwise it takes the `9D 7F` path (§3.13).
  - Delete User (`0x4af626`), on the same condition.
  - The end of a Manual download (`0x4b74a5`-`0x4b74e3`), after saving, when a stored setting is
    on (byte `0x63fcf5`, loaded from the settings at `0x50f4c4`). This works like the Auto-mode
    automatic delete.
- **Not seen in the capture:** `bum400_20261015_194301.pcap` has no `A1` (and no `9F 1F`), so
  SpO2 Assistant erased nothing there.
- **Confirmed on real hardware (2026-10-21, T-073):** `A1 00` then `A1 01` erases the Manual-mode
  recording -- both got a status-0 `D1` reply, and the recording was gone afterwards. Step 3
  (`A1 04`) is still unconfirmed; `fiedle400` never sends it (no known way to read the
  third-series flag in Manual mode).
- **`fiedle400 clear`** sends step 1 (`A1 00`), then step 2 (`A1 01`) once the device confirms the
  first, exactly as it does for the Auto-mode `9D 7F` path (§3.13); it never sends step 3 (`A1
  04`), since Manual mode has no known way to tell whether the third-series flag applies. Like
  the Auto-mode path, it verifies by re-listing afterwards rather than trusting the `D1` reply
  alone, and reports failure (exit 1) if the recording is still listed -- this has not yet been
  tried against a real device with an actual Manual-mode recording (`engine/device.py`
  `_clear_manual`, T-072).

### 3.15 Reverse-engineering `SpO2.exe` -- what works, what does not

Notes from the Manual-mode investigation, so the next person does not repeat
the dead ends. The local reference copy is `archive/bruteforce/SpO2.exe`
(gitignored): PE32, build timestamp 2025-03-13, 3301376 bytes, md5
`83d0b266626c1d7fa17a7a90c8ca13d9`.

**Check the build first.** There are at least three SpO2.exe builds in
circulation: this archived copy, the `SpO2 Assistant V3.0.5` installed on the
Windows laptop, and whichever build produced the relayed disassembly (user
confirmed 2026-10-15 that it is a different installation again). Addresses
quoted from one build mean nothing in another. Before chasing a cited
address, compare build timestamp and md5.

**Section table (this build), for VMA -> file offset:**

| Section | VMA | File offset | Size |
| :--- | :--- | :--- | :--- |
| `.text` | `0x401000` | `0x1000` | `0x1a98db` |
| `.rdata` | `0x5ab000` | `0x1ab000` | |
| `.data` | `0x5d7000` | `0x1d7000` | |
| `.rsrc` | `0x9aa000` | `0x22e000` | |

File offset = VMA - section VMA + section file offset. Get the table with
`objdump -h`, and disassemble with Python `capstone` in
`CS_ARCH_X86` / `CS_MODE_32`.

**Do not trust a linear capstone sweep of `.text`.** Starting one disassembly
at the section base and running to the end desyncs on the first data-in-code
or padding run and silently produces garbage for everything after it. A sweep
of this binary reported only 5 `and reg,7` instructions in 1.7 MB, which is
absurd for an MFC binary of this size; a raw byte scan found 29. Anything
concluded from a desynced sweep is worthless.

**Scan raw bytes instead -- it is alignment independent.** Search `.text` for
instruction encodings directly, then disassemble only the neighbourhoods that
hit. Useful encodings:

| Pattern | Encoding |
| :--- | :--- |
| `shr r32, 4` / `sar r32, 4` | `C1 /5 04` / `C1 /7 04` |
| `shr r8, 4` / `sar r8, 4` | `C0 /5 04` / `C0 /7 04` |
| `and al, imm8` | `24 ib` |
| `and r32, imm8` | `83 /4 ib` |
| `and r8, imm8` | `80 /4 ib` |
| `test al, imm8` | `A8 ib` |
| `cmp al, imm8` | `3C ib` |
| `mov r8, [reg+disp8]` | `8A /r disp8` |

**Verify every byte-pattern hit by disassembling around it.** Short patterns
match inside longer instructions constantly. All three `3C 7F`
("`cmp al, 0x7F`") hits in this binary are false positives sitting mid
instruction.

**Known decoy: DES at `0x42e2xx`.** A `[reg+5]` / `[reg+6]` byte-load pair
next to `shr` looks exactly like a record parser, but the surrounding
`0x0f0f0f0f` and `0x10101010` XOR/shift masks are the DES initial
permutation. The whole `0x42exxx`-`0x42fxxx` range is a crypto library.

**Scans that found nothing in this build** (all negative, all correctly
executed -- do not redo them): nibble-decode clusters pairing a shift-by-4
with a `0x0F`/`0x07` mask and a sign test within 64 bytes; signed 4-bit delta
lookup tables (`00 01 .. 07 00 FF FE ..` and variants) anywhere in `.text`,
`.rdata` or `.data`; all 22 `[reg+5]`/`[reg+6]` load pairs. This build does
not contain the Manual-mode delta decoder.

**What did work: deriving the format from the wire data.** The decode in
§3.14.F was solved empirically, not from the binary -- by tabulating each
candidate byte offset across all subframes and asking which column holds
physiologically possible values. Offset `0x05` holds 96/97/96/98 for SpO2 and
66/62/65/63 for Pulse; no other offset is close. With real hardware
available, this is faster and more reliable than disassembling a binary whose
build you cannot match.


## 4. Proprietary `.SpO2` Binary File Format

The Windows Contec SpO2 Assistant software and PO-400 use the `.SpO2` binary format for storing 1 Hz recording sessions (also supported by OSCAR for CPAP oximetry imports).

For the exhaustive specification, byte offsets, and reference code, see **[SPO2_FORMAT.md](SPO2_FORMAT.md)**.

| Offset | Type | Description |
| :--- | :--- | :--- |
| `0x0000` | `uint32_le` | Magic / Format ID (`0x00000358` / `856`) |
| `0x0004` | `uint32_le` | Format version (`0x00000001` / `1`) |
| `0x0008` – `0x0357` | `848 B` | Zero padding (`0x00`) |
| `0x0358` | `uint32_le` | Channel / Mode Flag (`0x00000001` / `1`) |
| `0x035C` – `0x035F` | `4 B` | Zero padding (`0x00`) |
| `0x0360` – `0x0365` | `6 B` | Protocol tag `"BLE\0"` (UTF-16LE: `42 00 4C 00 45 00`) |
| `0x0366` – `0x041F` | `186 B` | Zero padding (`0x00`) |
| `0x0420` | `uint32_le` | Start Year |
| `0x0424` | `uint32_le` | Start Month |
| `0x0428` | `uint32_le` | Start Day |
| `0x042C` | `uint32_le` | Start Hour |
| `0x0430` | `uint32_le` | Start Minute |
| `0x0434` | `uint32_le` | Start Second |
| `0x0438` | `uint32_le` | Total 1 Hz sample count ($N$) |
| `0x043C` | `uint8[2] × N` | `[SpO2 %, Pulse Rate BPM]` pairs per second (`0x7F, 0xFF` for probe-out/invalid) |
