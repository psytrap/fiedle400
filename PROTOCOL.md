# Pulox PO-400 / Contec USB-HID Protocol Specification

Bit- and byte-accurate wire protocol reference for the Pulox PO-400 (`VID_28E9&PID_028A`) pulse oximeter, reverse-engineered from `SpO2.exe` v2.0 and verified on USB bus captures and live hardware.

---

## 1. Core Framing Rules

1. **7-Bit Payload Restriction**: Data bytes carried in payloads must not set bit 7 (`0x00`..`0x7F` / 0..127) for UART backward compatibility. In `0xED` subframes, Bit 7 of the 21 payload bytes is stripped and stored across mask bytes 5, 6, and 7 (`m0`, `m1`, `m2`).
2. **Modulo-128 Checksum**: All request and subframe packets use a 7-bit additive checksum:
   `checksum = sum(bytes[0..N-1]) % 128` (or `sum(bytes[0..N-1]) & 0x7F`)
3. **14-Bit Integer Packing (7-bit Little-Endian)**:
   `value_14 = byte[0] | (byte[1] << 7)`
4. **28-Bit Integer Packing (Sample Count in 0xEC Header)**:
   `value_28 = b0 | (b1 << 7) | (b2 << 14) | (b3 << 21)`
5. **USB HID Report Size**: Outbound and inbound reports are 64 bytes fixed-length (`REPORT_SIZE = 64`), zero-padded.

---

## 2. Opcode & Response Registry

| Opcode | Name | Host Request | Device Response | Description |
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

---

## 3. Byte Maps

### 3.1 UNLOCK_HANDSHAKE (`0xA7` + `0xA2`)

#### Phase 1 Request (`0xA7`)
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Sync Prefix | `0x7D` | Protocol 0 sync marker |
| `0x01` | 1 byte | Channel ID | `0x81` | Target channel ID |
| `0x02` | 1 byte | Opcode | `0xA7` | Unlock Phase 1 |
| `0x03..0x08` | 6 bytes | Key / Padding | `0x80` × 6 | Unlock key bytes |
| `0x09` | 1 byte | Checksum | `0x20` | `sum(bytes[0..8]) % 128` |
| `0x0A..0x3F` | 54 bytes | Padding | `0x00` × 54 | Report padding |

#### Phase 2 Request (`0xA2`)
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Sync Prefix | `0x7D` | Protocol 0 sync marker |
| `0x01` | 1 byte | Channel ID | `0x81` | Target channel ID |
| `0x02` | 1 byte | Opcode | `0xA2` | Unlock Phase 2 |
| `0x03..0x08` | 6 bytes | Key / Padding | `0x80` × 6 | Unlock key bytes |
| `0x09` | 1 byte | Checksum | `0x1B` | `sum(bytes[0..8]) % 128` |
| `0x0A..0x3F` | 54 bytes | Padding | `0x00` × 54 | Report padding |

#### Device Response: ACK (`0xF0`)
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xF0` | Acknowledge |
| `0x01` | 1 byte | Status | `0x70` | `0x70` = Success / MCU unlocked |
| `0x02..0x3F` | 62 bytes | Padding | `0x00...` | Zero padding |

---

### 3.2 SESSION_RESET & QUERY_SESSIONS (`0x9C`)

#### SESSION_RESET Request
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0x9C` | Session iterator control |
| `0x01` | 1 byte | Sub-command | `0x80` | `0x80` = Reset iterator to start |
| `0x02` | 1 byte | Checksum | `0x1C` | `(0x9C + 0x80) % 128 = 0x1C` |

#### QUERY_SESSIONS Request
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0x9C` | Session query command |
| `0x01` | 1 byte | User / Slot ID | `0x01` | User 1 (Slot 1) |
| `0x02` | 1 byte | Checksum | `0x1D` | `(0x9C + 0x01) % 128 = 0x1D` |

#### Device Response: Session Header (`0xEC`, 64 Bytes)
| Offset | Length | Field | Format | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Header Opcode | `0xEC` | Session metadata packet identifier |
| `0x01` | 1 byte | Flags | Bitmask | Bit 6 (`0x40`): Data ready (1 = valid session). Bits 0..3: User slot ID |
| `0x02` | 1 byte | Total Segments | `uint8` | Total stored segments count |
| `0x03` | 1 byte | Segment Index | `uint8` | 1-based segment number |
| `0x04` | 1 byte | Year | `uint8` | Years since 2000 (`26` = 2026) |
| `0x05` | 1 byte | Month | `1..12` | Month |
| `0x06` | 1 byte | Day | `1..31` | Day of month |
| `0x07` | 1 byte | Hour | `0..23` | Start hour |
| `0x08` | 1 byte | Minute | `0..59` | Start minute |
| `0x09` | 1 byte | Second | `0..59` | Start second |
| `0x0A..0x0D` | 4 bytes | Sample Count | 28-bit LE | `B0 \| (B1<<7) \| (B2<<14) \| (B3<<21)`. 2 Hz samples. |
| `0x0E..0x1D` | 16 bytes | Username | ASCII | Null-terminated username string (e.g. `"user"`) |
| `0x1E..0x3F` | 34 bytes | Padding | `0x00...` | Reserved zero padding |

---

### 3.3 READ_RTC (`0x82`) & SET_RTC (`0x83`)

#### READ_RTC Request
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0x82` | Read clock |
| `0x01` | 1 byte | Checksum | `0x02` | `0x82 % 128 = 0x02` |

#### SET_RTC Request
| Offset | Length | Field | Range | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0x83` | Set clock |
| `0x01` | 1 byte | Year | `0..127` | Year since 2000 |
| `0x02` | 1 byte | Month | `1..12` | Month |
| `0x03` | 1 byte | Day | `1..31` | Day |
| `0x04` | 1 byte | Hour | `0..23` | Hour |
| `0x05` | 1 byte | Minute | `0..59` | Minute |
| `0x06` | 1 byte | Second | `0..59` | Second |
| `0x07` | 1 byte | Flags | `0x33` | Subsecond timing parameter |
| `0x08` | 1 byte | Reserved | `0x06` | Fixed parameter |
| `0x09` | 1 byte | Checksum | `0..127` | `sum(bytes[0..8]) % 128` |

#### Device Response: RTC Report (`0xF2`, 8 Bytes)
| Offset | Length | Field | Range | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xF2` | RTC response identifier |
| `0x01` | 1 byte | Year | `0..127` | Year since 2000 (YY) |
| `0x02` | 1 byte | Month | `1..12` | Month |
| `0x03` | 1 byte | Day | `1..31` | Day |
| `0x04` | 1 byte | Hour | `0..23` | Hour |
| `0x05` | 1 byte | Minute | `0..59` | Minute |
| `0x06` | 1 byte | Second | `0..59` | Second |
| `0x07` | 1 byte | Checksum | `0..127` | `sum(bytes[0..6]) % 128` |

---

### 3.4 DATA_STREAM_QUERY (`0x9B`) & Live Streaming (`0xEB`)

#### DATA_STREAM_QUERY Request
| Offset | Length | Field | Value | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0x9B` | Stream control |
| `0x01` | 1 byte | Control | `0x00` / `0x7F` | `0x00` = Start stream, `0x7F` = Stop stream |
| `0x02` | 1 byte | Checksum | `0x1B` / `0x1A` | `(0x9B + Control) % 128` |

#### Device Response: Live Sub-Frames (`0xEB`, 6 Bytes each)
Packed consecutively in 64-byte HID input reports:
| Offset | Length | Field | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Sync Opcode | `0xEB` | Live frame identifier |
| `0x01` | 1 byte | Status & Quality | Bitfield | Bit 0: Finger-out (`1` = probe off, `0` = OK)<br>Bits 1..3: Signal bars (0..8)<br>Bit 4: Beat trigger (1 = pulse tick) |
| `0x02` | 1 byte | Plethysmogram | `0..127` | Real-time PPG waveform curve amplitude |
| `0x03` | 1 byte | Pulse Rate | `0..254` | Pulse rate in BPM (`0xFF` = invalid) |
| `0x04` | 1 byte | SpO2 | `0..100` | Blood oxygen saturation % (`0x7F` = invalid) |
| `0x05` | 1 byte | Checksum | `0..127` | `sum(bytes[0..4]) % 128` |

---

### 3.5 Storage Transfer Commands (`0x9D`) & Subframes (`0xED`)

#### Storage Command Header Layout (64 Bytes Outbound)
```text
Byte: [0]  [1]   [2]   [3]     [4]    [5]     [6]      [7]    [8]   [9..63]
Val:  0x9D Mode  Type  User_ID Seg_ID Off_Lo  Off_Hi   0x00   Chk   0x00...
```

| Command | Mode | Type | User | Seg | Off_Lo | Off_Hi | Checksum | Description |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `STORAGE_INIT` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00` | `0x00` | `0x1C` | Initializes Flash read buffers |
| `READ_SPO2_BLOCK` | `0x04` | `0x01` | `0x01` | `0x01` | `0x00` | `0x00` | `0x24` | Reads SpO2 flash series |
| `READ_PULSE_BLOCK` | `0x04` | `0x02` | `0x01` | `0x01` | `0x00` | `0x00` | `0x25` | Reads Pulse Rate flash series |
| `SEGMENT_ACK` | `0x02` | `0x7F` | `0x7F` | `0x7F` | `0x00` | `0x00` | `0x1C` | Acknowledges session retrieval |

#### Device Response: Stored Data Sub-Frame (`0xED`, 30 Bytes each)
Each 64-byte HID input report carries 2 consecutive 30-byte subframes (60 bytes total) plus 4 bytes trailing padding:

| Offset | Length | Field | Format | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xED` | Storage subframe sync marker |
| `0x01` | 1 byte | Mode | `0x04` | Flash block transfer mode |
| `0x02` | 1 byte | Data Type | `0x01` / `0x02` | `0x01` = SpO2 series, `0x02` = Pulse Rate series |
| `0x03..0x04` | 2 bytes | Sequence Index | 14-bit LE | `(Byte[4] << 7) \| Byte[3]` (0-based subframe counter) |
| `0x05` | 1 byte | MSB Mask 0 | Bitmask | Restores Bit 7 for payload bytes `0x08..0x0E` |
| `0x06` | 1 byte | MSB Mask 1 | Bitmask | Restores Bit 7 for payload bytes `0x0F..0x15` |
| `0x07` | 1 byte | MSB Mask 2 | Bitmask | Restores Bit 7 for payload bytes `0x16..0x1C` |
| `0x08..0x1C` | 21 bytes | Compressed Data | 42 nibbles | Delta-compressed 2 Hz samples (see below) |
| `0x1D` | 1 byte | Checksum | `0..127` | `sum(bytes[0..28]) % 128` |

#### MSB Unmasking Algorithm
Payload bytes `0x08..0x1C` (indices 8..28) are 7-bit encoded. Bit 7 is restored using `m0` (byte 5), `m1` (byte 6), and `m2` (byte 7):
```python
unmasked = bytearray(payload[8:29])
for i in range(7):
    if (m0 >> i) & 1: unmasked[i] |= 0x80
    if (m1 >> i) & 1: unmasked[i + 7] |= 0x80
    if (m2 >> i) & 1: unmasked[i + 14] |= 0x80
```

#### Delta-Nibble Decompression
1. **Dynamic Baseline Initialization (`0xF_ 0xF_` Escape)**:
   - When a byte has high nibble `0xF_`, it pairs with the next `0xF_` byte to establish the dynamic baseline:
     $$\text{Base} = ((B_1 \ \& \ 0\text{x}0\text{F}) \ll 4) \mid (B_2 \ \& \ 0\text{x}0\text{F})$$
     *(e.g., `0xF6 0xF2` $\implies \text{Base}_{\text{SpO2}} = 98\%$; `0xF3 0xFA` $\implies \text{Base}_{\text{HR}} = 58\text{ BPM}$)*
   - **Cross-Subframe Split Base**: If $B_1$ occurs at byte index 28 (end of subframe), $B_2$ is read from index 8 of the next subframe.
2. **Stream Terminator**: `0xFF 0xFF` indicates the end of recorded flash data.
3. **Delta-Nibble Extraction (2 Hz Half-Second Samples)**:
   - Each byte carries two 4-bit nibbles:
     $$\text{Sample}_1 = \text{Base} - (B \gg 4)$$
     $$\text{Sample}_2 = \text{Base} - (B \ \& \ 0\text{x}0\text{F}) \quad (\text{skipped if nibble is } 0\text{x}0\text{F} \text{ padding})$$
   - Note: $B = 0\text{x}00$ represents $\Delta = 0$ ($\text{Sample} = \text{Base}$). Zero bytes are valid data and must **not** be dropped.
4. **End-of-Data Sentinel**: A subframe with `mode = 0x00`, `seq = 0`, and masks containing `0x7F` indicates an uninitialized flash segment and signals immediate termination.

---

### 3.6 QUERY_DEVICE_INFO (`0x81` / `0xAD`)

#### Request (`0x81`)
`[0x81, 0x01]` (Checksum: `0x01`)

#### Device Response (`0xF1`, 10 Bytes)
| Offset | Length | Field | Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xF1` | Device info header |
| `0x01..0x08` | 8 bytes | Model String | ASCII | `"50F     "` (CMS50F / PO-400) |
| `0x09` | 1 byte | Checksum | `0x3C` | `sum(bytes[0..8]) % 128` |

---

### 3.7 FIRMWARE_QUERY (`0x80`)

#### Request (`0x80`)
`[0x80, 0x00]` (Checksum: `0x00`)

#### Device Response (`0xCF`, 10 Bytes)
| Offset | Length | Field | Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xCF` | Firmware info header |
| `0x01..0x08` | 8 bytes | Version String | ASCII | `"V3.1    "` |
| `0x09` | 1 byte | Checksum | `0..127` | `sum(bytes[0..8]) % 128` |

---

### 3.8 SERIAL_PROFILE_QUERY (`0x8E`)

#### Request (`0x8E`)
| Sub-Index | Request Bytes | Description |
| :---: | :--- | :--- |
| `0x03` | `8E 03 11` | Username query |
| `0x06` | `8E 06 14` | Profile query |
| `0x07` | `8E 07 15` | Serial number query |

#### Device Response (`0xFE`, 11 Bytes)
| Offset | Length | Field | Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xFE` | Profile response |
| `0x01` | 1 byte | Sub-Index Echo | `uint8` | Confirms requested index |
| `0x02..0x09` | 8 bytes | Text String | ASCII | Username or serial number string |
| `0x0A` | 1 byte | Checksum | `0..127` | `sum(bytes[0..9]) % 128` |

---

### 3.9 FLASH_GEOMETRY_QUERY (`0x8F`)

#### Request (`0x8F`)
`[0x8F, 0x04, 0x00, 0x13]` (Checksum: `0x13`)

#### Device Response (`0xEF`, 8 Bytes)
| Offset | Length | Field | Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xEF` | Flash geometry header |
| `0x01` | 1 byte | Sector Count | `uint8` | Number of flash sectors |
| `0x02..0x03` | 2 bytes | Block Size | 14-bit LE | Block size in bytes (64 or 256) |
| `0x04..0x06` | 3 bytes | Capacity | 21-bit LE | Total capacity |
| `0x07` | 1 byte | Checksum | `0..127` | `sum(bytes[0..6]) % 128` |

---

### 3.10 FLASH_SECTOR_QUERY (`0x94`)

#### Request (`0x94`)
`[0x94, 0x14]` (Checksum: `0x14`)

#### Device Response (`0xD4`, 18 Bytes)
| Offset | Length | Field | Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xD4` | Sector layout header |
| `0x01` | 1 byte | Total Blocks | `uint8` | Flash blocks count |
| `0x02..0x03` | 2 bytes | Block Pages | 14-bit LE | Pages per block |
| `0x04..0x10` | 13 bytes | Sector Map | Bytes | Sector allocation bitmask |
| `0x11` | 1 byte | Checksum | `0..127` | `sum(bytes[0..16]) % 128` |

---

### 3.11 USER_METADATA_QUERY (`0x90`)

#### Request (`0x90`)
`[0x90, 0x06, 0x16]` (Checksum: `0x16`)

#### Device Response (`0xE0`, 7 Bytes)
| Offset | Length | Field | Range | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 byte | Opcode | `0xE0` | Alarm metadata header |
| `0x01` | 1 byte | Sub-Index Echo | `0x06` | Echo of requested index |
| `0x02` | 1 byte | SpO2 Low Limit | `0..100 %` | Lower SpO2 alarm limit |
| `0x03` | 1 byte | SpO2 High Limit | `0..100 %` | Upper SpO2 alarm limit |
| `0x04` | 1 byte | PR Low Limit | `25..250 BPM` | Lower Pulse Rate alarm limit |
| `0x05` | 1 byte | PR High Limit | `25..250 BPM` | Upper Pulse Rate alarm limit |
| `0x06` | 1 byte | Checksum | `0..127` | `sum(bytes[0..5]) % 128` |

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

## 4. Proprietary `.SpO2` Binary File Format

The Windows Contec SpO2 Assistant exports decoded sessions in `.SpO2` format:

| Offset | Size | Type | Description |
| :--- | :--- | :--- | :--- |
| `0x0000` | 4 bytes | uint32_le | File size hint |
| `0x0004` | 4 bytes | uint32_le | Format version (`0x01`) |
| `0x0420` | 4 bytes | uint32_le | Start Year |
| `0x0424` | 4 bytes | uint32_le | Start Month |
| `0x0428` | 4 bytes | uint32_le | Start Day |
| `0x042C` | 4 bytes | uint32_le | Start Hour |
| `0x0430` | 4 bytes | uint32_le | Start Minute |
| `0x0434` | 4 bytes | uint32_le | Start Second |
| `0x0438` | 4 bytes | uint32_le | Total 1 Hz sample count |
| `0x043C` | N×2 bytes | uint8[2] | `[SpO2 %, Pulse Rate BPM]` pairs per second |

