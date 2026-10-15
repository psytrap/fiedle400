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
   `value_28 = b0 | (b1 << 7) | (b2 << 14) | (b3 << 21)` -- counts raw 2 Hz half-second samples, **not** seconds or 1 Hz records (confirmed: psytrap, 2026-10-15; see §3.2 and §3.5.3, and RELEASE_PLAN.md T3). Real duration/record count = `value_28 // 2`.
5. **USB HID Report Size**: Outbound and inbound reports are 64 bytes fixed-length (`REPORT_SIZE = 64`), zero-padded.

---

## 2. Command & Response Registry

> [!IMPORTANT]
> **Universal Protocol Principle: MSB Control vs. Data Distinction**
> Across the entire protocol, the Most Significant Bit (Bit 7) serves as the universal delimiter between control and data:
> - **`MSB = 1` (`0x80..0xFF`)**: **Opcode / Control Character** — All host request opcodes, device response markers, frame sync headers, and in-stream control escapes strictly have Bit 7 set.
> - **`MSB = 0` (`0x00..0x7F`)**: **Data Payload** — All parameters, counters, checksums, and in-stream payload bytes are restricted to 7 bits (masked with `0x7F`) to prevent accidental collisions with opcodes or frame boundaries.

### 2.1 Outbound Host Request Commands
| Opcode | Name | Host Request (Hex) | Expected Response | Description |
| :---: | :--- | :--- | :---: | :--- |
| **0xA7 + 0xA2** | `UNLOCK_HANDSHAKE` | `7D 81 A7 80...` & `7D 81 A2 80...` | `0xF0` | Unlocks MCU state machine (ACK `F0 70`) |
| **0x9C [0x80]** | `SESSION_RESET` | `7D 81 9C 80 00 1C` | `0xF0` / `0xEC` | Resets session iterator to slot 0 |
| **0x9C [0x01]** | `QUERY_SESSIONS` | `9C 01 1D` | `0xEC` | Queries session metadata header for slot 1 |
| **0x82** | `READ_RTC` | `82 02` | `0xF2` | Reads device clock (YY/MM/DD HH:MM:SS) |
| **0x83** | `SET_RTC` | `83 [YY MM DD HH MM SS 33 06] [chk]` | `0xF2` / `0xF0` | Synchronizes device Real-Time Clock |
| **0x9B [0x00]** | `DATA_STREAM_QUERY` | `9B 00 1B` (Start) / `9B 7F 1A` (Stop) | `0xEB` | Controls live streaming (6-byte frames) |
| **0x9D [0x02]** | `STORAGE_INIT` | `9D 02 7F 7F 7F 00 00 1C` | `0xF0` | Initializes flash read buffers |
| **0x9D [0x04 0x01]** | `READ_SPO2_BLOCK` | `9D 04 01 01 01 00 00 00 24` | `0xED` | Requests SpO2 series block |
| **0x9D [0x04 0x02]** | `READ_PULSE_BLOCK` | `9D 04 02 01 01 00 00 00 25` | `0xED` | Requests Pulse Rate series block |
| **0x9D [0x02]** | `SEGMENT_ACK` | `9D 02 7F 7F 7F 00 00 1C` | `0xF0` | Non-destructive session download acknowledge |
| **0x81 / 0xAD** | `QUERY_DEVICE_INFO` | `81 01` / `7D 81 AD 80...` | `0xF1` | Hardware model descriptor (`"50F"`) |
| **0x80 / 0x81** | `FIRMWARE_QUERY` | `80 00` / `81 01` | `0xCF` | Firmware version descriptor string |
| **0x8E [0x03]** | `SERIAL_PROFILE_QUERY` | `8E 03 11` (User), `8E 06 14`, `8E 07 15` | `0xFE` | User profile name and serial number |
| **0x8F / 0x9F** | `FLASH_GEOMETRY_QUERY` | `8F 04 00 13` | `0xEF` | Flash topology & block size |
| **0x90 [0x06]** | `USER_METADATA_QUERY` | `90 06 16` | `0xE0` | Alarm thresholds (SpO2 High/Low, PR High/Low) |
| **0x94** | `FLASH_SECTOR_QUERY` | `94 14` | `0xD4` | Flash sector layout parameters |
| **0xA5** | `SESSION_SELECT` | `7D 81 A5 [id] [chk]` | `0xF0` | Selects session index (serial-stream devices) |
| **0xA6** | `SESSION_DOWNLOAD` | `7D 81 A6 [chk]` | `0xEB` | Starts stream download (serial-stream devices) |
| **0xAA / 0x91** | `FLASH_CLEAR` | `7D 81 AA...` / `91 01 12` | `0xF0` | Flash erase / User erase (Destructive) |

### 2.2 Inbound Device Responses
| Response Header | Name | Payload Length | Triggering Command | Description |
| :---: | :--- | :---: | :---: | :--- |
| **`0xF0`** | `COMMAND_ACK` | 2 B (HID-aligned) | `0xA7`, `0xA2`, `0x9D 0x02`, `0x83` | Acknowledgment report. Byte 1 = `0x70` indicates success / MCU unlocked. |
| **`0xEC`** | `SESSION_INDEX` | 21 B (HID-aligned) | `0x9C [0x01]` | Session metadata index: User ID, Session ID, Start Date/Time, 28-bit Sample Count, Profile Name. |
| **`0xED`** | `STORAGE_SUBFRAME` | 30 B (stream)* | `0x9D 0x04 [0x01/0x02]` | Stored session data: 14-bit sequence, 3 MSB masks (`m0..m2`), 21 B delta-nibbles. |
| **`0xEB`** | `LIVE_STREAM` | 6 B (HID-aligned, up to 3×) | `0x9B [0x00]` / `0xA6` | Real-time streaming sample sub-chunks: Status flags, PPG waveform bar height, Pulse Rate BPM, SpO2 %. |
| **`0xF2`** | `RTC_REPORT` | 8 B (HID-aligned) | `0x82`, `0x83` | Real-Time Clock date and time: Year, Month, Day, Hour, Minute, Second, Checksum. |
| **`0xF1`** | `DEVICE_INFO` | 10 B (HID-aligned) | `0xAD`, `0x81` | Hardware model descriptor ASCII string (e.g. `"50F     "`). |
| **`0xCF` / `0x81`** | `FIRMWARE_INFO` | 10 B (HID-aligned) | `0x80`, `0x81` | Firmware version descriptor ASCII string (e.g. `"V3.1    "`). |
| **`0xFE`** | `PROFILE_INFO` | 11 B (HID-aligned) | `0x8E` | User profile ASCII string (`"   user "`) or serial number string. |
| **`0xEF`** | `FLASH_GEOMETRY` | 8 B (HID-aligned) | `0x8F`, `0x9F` | Flash memory geometry: sector count, block size (14-bit LE), capacity. |
| **`0xD4`** | `FLASH_SECTOR` | 18 B (HID-aligned) | `0x94` | Flash sector layout: total blocks, block pages, sector allocation bitmask. |
| **`0xE0`** | `USER_METADATA` | 7 B (HID-aligned) | `0x90 [0x06]` | User alarm thresholds: SpO2 Low/High (%), PR Low/High (BPM). |

\*) **Framing & Alignment**:
- **HID-aligned**: Message starts strictly at Byte 0 of the 64-byte USB report; remaining bytes are zero-padded (`0x00`).
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

Not re-verified byte-for-byte live in this pass (the subsequent `0xA0`
request succeeded without one being read back, so the handshake works
functionally either way); carried over from the earlier draft.

---

### 3.2 SESSION_RESET & QUERY_SESSIONS (`0x9C`)

#### SESSION_RESET Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9C` | Session iterator control |
| `0x01` | Sub-command | `0x80` | `0x80` = Reset iterator to start |
| `0x02` | Checksum | `0x1C` | `(0x9C + 0x80) % 128 = 0x1C` |

#### QUERY_SESSIONS Request
| Offset | Field | Value | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9C` | Session query command |
| `0x01` | User / Slot ID | `0x01` | User 1 (Slot 1) |
| `0x02` | Checksum | `0x1D` | `(0x9C + 0x01) % 128 = 0x1D` |

#### Device Response: Session Header (`0xEC`, 64 Bytes)
| Offset | Field | Format | Description |
| :--- | :--- | :--- | :--- |
| `0x00` | Header Opcode | `0xEC` | Session metadata packet identifier |
| `0x01` | Flags | Bitmask | Bit 6 (`0x40`): Data ready (1 = valid session). Bits 0..3: User slot ID |
| `0x02` | Total Segments | `uint8` | Total stored segments count |
| `0x03` | Segment Index | `uint8` | 1-based segment number |
| `0x04` | Year | `uint8` | Years since 2000 (`26` = 2026) |
| `0x05` | Month | `1..12` | Month |
| `0x06` | Day | `1..31` | Day of month |
| `0x07` | Hour | `0..23` | Start hour |
| `0x08` | Minute | `0..59` | Start minute |
| `0x09` | Second | `0..59` | Start second |
| `0x0A..0x0D` | Raw Sample Count | 28-bit LE | `B0 \| (B1<<7) \| (B2<<14) \| (B3<<21)`. **Not seconds.** Counts raw 2 Hz half-second samples (confirmed: psytrap, 2026-10-15; previously mislabelled here as "1 Hz records", see RELEASE_PLAN.md T3). `duration_sec = raw_count // 2`. |
| `0x0E..0x1D` | Username | ASCII | Null-terminated username string (e.g. `"user"`) |
| `0x1E..0x3F` | Padding | `0x00...` | Reserved zero padding |

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

---

### 3.5 Storage Transfer Commands (`0x9D`) & Subframes (`0xED`)

#### Storage Command Request (`0x9D`, 64 Bytes Outbound)

| Offset | Field | Value / Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0x9D` | Storage transfer command opcode |
| `0x01` | Mode | `0x02` / `0x04` | `0x02` = Init / ACK, `0x04` = Read block |
| `0x02` | Data Type | `0x01` / `0x02` / `0x7F` | `0x01` = SpO2 series, `0x02` = Pulse Rate, `0x7F` = Init / ACK |
| `0x03` | User ID | `0x01` / `0x7F` | User slot ID (`0x7F` for Init / ACK) |
| `0x04` | Segment ID | `0x01` / `0x7F` | Session segment ID (`0x7F` for Init / ACK) |
| `0x05` | Offset Low | `0x00..0x7F` | Sample offset (bits 0..6) -- **not** a block/page index, see note below |
| `0x06` | Offset High | `0x00..0x7F` | Sample offset (bits 7..13) |
| `0x07` | Reserved | `0x00` | Fixed zero |
| `0x08` | Checksum | `0..127` | `sum(bytes[0..7]) % 128` |
| `0x09..0x3F` | Padding | `0x00...` | Reserved zero padding |

#### Command Parameters
| Command | Mode `[0x01]` | Type `[0x02]` | User `[0x03]` | Seg `[0x04]` | Offset `[0x05..0x06]` | Checksum `[0x08]` | Description |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `STORAGE_INIT` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00 0x00` | `0x1C` | Initializes Flash read buffers |
| `READ_SPO2_BLOCK` | `0x04` | `0x01` | `0x01` | `0x01` | `0x00 0x00` | `0x24` | Reads SpO2 flash series |
| `READ_PULSE_BLOCK` | `0x04` | `0x02` | `0x01` | `0x01` | `0x00 0x00` | `0x25` | Reads Pulse Rate flash series |
| `SEGMENT_ACK` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00 0x00` | `0x1C` | Acknowledges session retrieval |

> [!IMPORTANT]
> **The offset is a raw-sample sliding window, not a page index** (confirmed: psytrap, 2026-10-15,
> by exact byte comparison against a real device). Requesting offset `k` returns the session's data
> starting `k` *raw 2 Hz samples* in, not the k-th block of fresh data: `window(k)[i] == window(0)[i+k]`
> for every `i`, on both series. A client that requests offsets `0, 1, 2, ...` and concatenates the
> replies as if they were successive pages receives overlapping, re-shifted data, not new samples --
> this is exactly how `fiedle400`'s own download logic padded a 107-second (214-raw-sample, see §3.2)
> session out to 214 "records" before the bug was found (RELEASE_PLAN.md §3d, T6). The correct read is a
> single request at offset 0 for the whole stored series; advancing the offset is for resuming a
> partial read, not paging through additional data.

> **Boundary probe (psytrap's laptop, 2026-10-15, `tests/fixtures/probe.trace.json`, one 214-sample session).**
> SpO2 reads at offsets 0, 1, 2, 50, 107, 150, 213, 214, 215, 300 show that every reply runs from the offset
> **to the end of the stored data** (214, 213, 212, 164, 107, 64 and 1 values; all equal to `window(0)[k:]`).
> At offset == stored samples (214) the device sends one frame of `0xFF` filler (`ED 04 01 00 00 7B 7F 7F ...`,
> which decodes to the `0xFF 0xFF` terminator, no samples); beyond it (215, 300) it sends **nothing**. How a
> session longer than one reply (more than the 6 frames seen so far) is split is still unrecorded; until then
> `fiedle400` continues at offset `2 * records_so_far`, so a split reply is read correctly, and stops on a
> reply that adds no record (the end marker, or silence).
> The short final frame of a reply has all three MSB masks set (`7F`), so mask byte `m2` is `0x7F` there;
> it is *not* a status flag (RELEASE_PLAN.md §3d, T1). Finger-out shows up as out-of-range *values* (SpO2 127,
> pulse 255), see `analysis/bum400_20260906_100516.md` §4.

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
4. **End-of-Data Sentinel**: A subframe with `mode = 0x00`, `seq = 0`, and masks containing `0x7F` indicates an uninitialized flash segment and signals immediate termination.

---

> [!IMPORTANT]
> **A query below can be answered with a bare `COMMAND_ACK` (`0xF0 0x70`, see §2.2) instead of its
> documented response** (confirmed: psytrap, 2026-10-15, on a real device for the `0xAD` and `9E 40 04`
> variants of these queries; RELEASE_PLAN.md §3d, T7). This is not a framing error -- it is a valid,
> differently-shaped reply, and a client must check the response's own opcode byte before parsing it as
> the expected structure. Code that assumes the documented opcode and blindly parses whatever arrives
> will misread the ACK's status byte as field data, or pick up an unrelated response left over from a
> different query (on the affected device, this is how the model string from §3.6 ended up printed as a
> serial number, and the ACK's `0x70` status byte as a flash geometry value). The safe fallback when the
> response opcode does not match is "not reported", never a value synthesised from the wrong bytes.

### 3.6 QUERY_DEVICE_INFO (`0x81` / `0xAD`)

#### Request (`0x81`)
`[0x81, 0x01]` (Checksum: `0x01`)

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

---

### 3.8 SERIAL_PROFILE_QUERY (`0x8E`)

#### Request (`0x8E`)
| Sub-Index | Request Bytes | Description |
| :---: | :--- | :--- |
| `0x03` | `8E 03 11` | Username query |
| `0x06` | `8E 06 14` | Profile query |
| `0x07` | `8E 07 15` | Serial number query |

#### Device Response (`0xFE`, 11 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xFE` | Profile response |
| `0x01` | Sub-Index Echo | `uint8` | Confirms requested index |
| `0x02..0x09` | Text String | ASCII | Username or serial number string |
| `0x0A` | Checksum | `0..127` | `sum(bytes[0..9]) % 128` |

---

### 3.9 FLASH_GEOMETRY_QUERY (`0x8F`)

#### Request (`0x8F`)
`[0x8F, 0x04, 0x00, 0x13]` (Checksum: `0x13`)

#### Device Response (`0xEF`, 8 Bytes)
| Offset | Field | Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xEF` | Flash geometry header |
| `0x01` | Sector Count | `uint8` | Number of flash sectors |
| `0x02..0x03` | Block Size | 14-bit LE | Block size in bytes (64 or 256) |
| `0x04..0x06` | Capacity | 21-bit LE | Total capacity |
| `0x07` | Checksum | `0..127` | `sum(bytes[0..6]) % 128` |

---

### 3.10 FLASH_SECTOR_QUERY (`0x94`)

#### Request (`0x94`)
`[0x94, 0x14]` (Checksum: `0x14`)

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

---

### 3.12 SESSION_SELECT (`0xA5`) & SESSION_DOWNLOAD (`0xA6`)

Used on serial-stream device models:
- **Select Session**: `[0x7D, 0x81, 0xA5, session_id, chk]`
- **Start Download**: `[0x7D, 0x81, 0xA6, 0x00, chk]`
- **Response**: Device returns `0xF0 0x70` ACK or begins streaming `0xEB` frames.

---

### 3.13 FLASH_CLEAR (`0xAA` & `0x91`..`0x96`)

> [!CAUTION]
> **Destructive Operations**:
> - `0xAA`: Completely erases all flash memory partitions.
> - `0x91`..`0x96`: Erases recorded session data for User 1..6.

- **Full Erase Request**: `[0x7D, 0x81, 0xAA, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x28]`
- **User Erase Request**: `[0x91, 0x01, 0x12]` (User 1)
- **Response**: `[0xF0, 0x70]` upon completion.

---

### 3.14 Manual Recording Protocol (`0xA0`/`0xD0`, `0xA2`/`0xD2`, `0xA3`/`0xD3`, `0xA7`/`0xD8`)

> [!IMPORTANT]
> **Documented, not yet implemented.** Found 2026-10-15 via a live USB capture
> of the vendor's own SpO2 Assistant software reading a **Manual-mode**
> recording, cross-referenced against its disassembly (`SpO2.exe` @
> `0x004c4875` for the delta decoder). This is a **separate, parallel**
> protocol from the `0x9C`/`0x9D` flash-index commands used everywhere else
> in this document, which only ever read **Auto-mode** sessions -- that is
> the root cause of the Manual-mode session visibility question in
> `RELEASE_PLAN.md` §3d: Manual-mode data was never reachable via `0x9C`/
> `0x9D` at all, by design, not by a bug or a missing argument. No code in
> this project implements the commands below yet.
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
| `0x01` | Unknown | `0x00` in every sample seen | Not yet identified -- always zero so far |
| `0x02..0x04` | Date | `YY MM DD` | e.g. `1A 0A 0F` = 2026-10-15 (`0x1A` = 26 -> `2000+26`) |
| `0x05..0x07` | Time | `HH MM SS` | e.g. `13 22 10` = 19:34:16 |
| `0x08..0x0A` | Duration (s) | 3 bytes, direct (not the 28-bit packing used elsewhere) | e.g. `00 00 3B` = 59 s. **Confirmed live (2026-10-15) against the real device with the offsets above -- the original draft had these one byte too early, missing the unknown byte at `0x01`.** |

#### B. SpO2 Data Block (`0xA3` -> `0xD3`)

Request: `A3 00 00 00 23` (start at subframe 0; the last two bytes are a
14-bit-packed subframe offset per §1.3, `00 00` = offset 0).

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

#### F. Delta-Nibble Decompression (`0xD3` / `0xD2` payload) -- CONFIRMED

**Solved and live-verified 2026-10-15.** Every one of the 8 data subframes in
the reference capture decodes to physiologically valid values with no
offset, scaling or post-correction.

Within a 20-byte subframe `[opcode][seq][00][16 data bytes][checksum]`:

| Record offset | Field | Meaning |
| :--- | :--- | :--- |
| `0x03..0x04` | Unknown | Not needed for decoding; see note below |
| `0x05` | **Base value** | First sample, as a direct value: SpO2 in %, Pulse in bpm. `0x7F` here means the whole subframe is "no finger / no signal". |
| `0x06..0x12` | Delta stream | 13 bytes, 2 samples per byte, high nibble first |
| `0x13` | Checksum | `sum(bytes[0x00..0x12]) % 128` |

So one subframe carries at most **27 samples** (1 base + 13x2 deltas).

Each nibble is sign-and-magnitude: **bit 3 = sign** (1 = negative),
**bits 2..0 = magnitude** (0-7). The value chain is running, not
fixed-base: `S_n = S_(n-1) +/- magnitude`.

Two distinct terminators, checked in this order:

1. **Whole byte `0x7F`** -- padding, the subframe ends here. Checked
   *before* splitting into nibbles.
2. **Nibble `0xF`** -- end marker for an odd sample count; the subframe
   ends at that half-byte.

Reference implementation:

```python
SENTINEL = 0x7F

def decode_subframe(rec):            # rec = the 20 bytes
    base = rec[5]
    if base == SENTINEL:
        return None                  # no finger for this whole subframe
    values, cur = [base], base
    for byte in rec[6:19]:
        if byte == SENTINEL:         # byte-level padding -> end
            break
        for shift in (4, 0):         # high nibble first
            nib = (byte >> shift) & 0xF
            if nib == 0xF:           # odd-count end marker
                return values
            cur += -(nib & 7) if (nib & 8) else (nib & 7)
            values.append(cur)
    return values
```

Decoded reference capture (2026-10-15, 7 subframes per series):

| seq | SpO2 | Pulse |
| :--- | :--- | :--- |
| 0 | no finger | no finger |
| 1 | 96 flat (16 samples) | 66-67 (16) |
| 2 | no finger | no finger |
| 3 | 97 -> 98 (27) | 62 -> 65 (27) |
| 4 | 96 -> 100 (9) | 65, ending 64 (9) |
| 5 | no finger | no finger |
| 6 | 98 -> 99 (7) | 63 -> 64 (7) |

Totals: SpO2 96-100%, Pulse 62-67 bpm, 59 samples with signal across a
140-sample (~2m20s) timeline.

> [!NOTE]
> **How the earlier wrong decode went wrong.** Two prior attempts read the
> base from record offset `0x03` instead of `0x05`. That inflated SpO2 to
> 116-127 (apparently "over the 100% ceiling") and produced negative Pulse
> values, which in turn motivated a bogus "subtract a constant 27-28"
> hypothesis and a bogus "ramp-up transient" reading of subframes 1 and 3.
> All of that was the off-by-two, nothing else. The relayed disassembly note
> "byte `0x04` of the data region is the base value" was **correct** --
> counting the data region from the `seq` byte (`rec[1]`), index 4 is exactly
> `rec[5]`. Read field indices against a stated origin before trusting them.

> [!NOTE]
> **Updated 2026-10-15 against a second relayed disassembly pass and a
> fresh live re-pull of the same stored recording (byte-identical to the
> earlier capture, confirming it is deterministic).**
>
> (a) **Record offset `0x04` is not a channel ID.** A relayed disassembly
> claimed `rec[0x03]` (its own indexing counts from the `seq` byte, so this
> is `rec[4]` in this document's indexing) is a constant hardware channel
> marker, `0x08` for SpO2 / `0x04` for Pulse. Checked directly against the
> live capture: it is not constant. Across the four real SpO2 subframes it
> reads `0x7C, 0x00, 0x7F, 0x7F`; across Pulse, `0x7D, 0x00, 0x7F, 0x7F`.
> Still unidentified, and definitely not a fixed per-series tag.
>
> A follow-up disassembly pass adds a negative finding rather than a
> positive one: the host (`SpO2.exe`) decode path never reads this byte at
> all anywhere in the loop -- it reads bytes 0/1/2 (opcode/seq/reserved)
> and then jumps straight to byte 4 for the base value. That is consistent
> with, not a resolution of, the open question: the *host* ignores it, but
> what the *firmware* actually writes there -- a leading candidate guess is
> per-sample status/quality bits from the MCU, unconfirmed -- is still
> unidentified. Documenting it as unidentified rather than guessing is the
> correct state here, not a gap to be filled in by assertion.
>
> (b) **High-nibble-first is now corroborated two ways.** The empirical
> smoothness check in this capture was a near-exact tie (23 vs 24) and could
> not settle it alone. A second, independently relayed disassembly
> description of the decode loop matches this document's nibble math
> exactly (sign at bit 7 of the byte / bit 3 of the low nibble, magnitude in
> the remaining 3 bits, high nibble consumed first) -- consistent with, not
> derived from, the empirical tie-break already in place. Treat as settled
> unless a sharp-transition capture disagrees.
>
> (c) **Duration vs. sample count: a credible mechanism was offered, not
> independently confirmed.** The same relayed source claims the device's
> own reader stops consuming samples once a running count reaches the
> header's duration value, and that everything past that point -- even
> same-value deltas that look like genuine flat readings -- is block
> padding the reader is instructed to discard. That would reconcile 41 s of
> real data with a 59-sample decoded stream without requiring a
> terminator at the cutoff. It cannot be checked from the raw bytes alone:
> `0x00` deltas are indistinguishable from genuine "no change" samples by
> design, which is exactly why this was ambiguous to begin with. A
> precisely timed fresh recording (exact duration by stopwatch, compared
> against the resulting header value and decoded sample count) is still
> the only way to settle this directly.
>
> (d) `0x7F` as padding is ambiguous with a legitimate `+7, -7` delta pair;
> the device appears to reserve it, but a capture with large swings would
> confirm.


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
