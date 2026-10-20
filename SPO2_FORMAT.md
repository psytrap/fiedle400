# Contec / Pulsox PO-400 `.SpO2` Binary File Format Specification

## 1. Overview

The `.SpO2` (or `.spo2`) binary format is the proprietary recording format produced and consumed by **Contec Medical Systems** software (specifically **SpO2 Assistant**) for pulse oximeters such as the CMS-50 series, CMS-60D, and Pulsox PO-400.

This format stores continuous 1 Hz pulse oximetry recordings consisting of:
- Blood Oxygen Saturation ($\text{SpO}_2$) in percent ($0 - 100\%$).
- Pulse Rate (PR / Heart Rate) in beats per minute ($0 - 250\text{ bpm}$).

It is also recognized and imported by open-source sleep analysis software such as **OSCAR** (Open Source CPAP Analysis Reporter) via its oximetry import wizard.

---

## 2. File Structure

A `.SpO2` file consists of two primary segments:
1. **Fixed Header**: Exactly 1,084 bytes (`0x043C` bytes).
2. **Data Payload**: Exactly $N \times 2$ bytes, where $N$ is the number of 1-second sample records.

$$\text{Total File Size} = 1084 + (N \times 2) \text{ bytes}$$

---

## 3. Header Specification (1,084 Bytes / `0x043C`)

All multi-byte numeric fields are stored in **Little-Endian** byte order (`<I`).

| Byte Offset | Size | Type | Field Name | Description / Valid Values |
| :--- | :---: | :--- | :--- | :--- |
| `0x0000` | 4 B | `uint32_le` | **Magic / Format ID** | Fixed constant `0x00000358` (decimal `856`). Validated by `SpO2.exe` at offset `0x4E2277`. |
| `0x0004` | 4 B | `uint32_le` | **Format Version** | Fixed constant `0x00000001` (Version 1). |
| `0x0008` – `0x0357` | 848 B | `bytes` | **Reserved Block 1** | Zero-filled (`0x00`). |
| `0x0358` | 4 B | `uint32_le` | **Device / Stream Flag** | Fixed constant `0x00000001` (Active channel / mode flag). |
| `0x035C` | 4 B | `bytes` | **Reserved Block 2** | Zero-filled (`0x00`). |
| `0x0360` – `0x0365` | 6 B | `bytes` | **Protocol / Transport Tag** | UTF-16LE string `b"B\x00L\x00E\x00"` (`"BLE\0"`). |
| `0x0366` – `0x041F` | 186 B | `bytes` | **Reserved Block 3** | Zero-filled (`0x00`). |
| `0x0420` | 4 B | `uint32_le` | **Start Year** | Year of recording start (e.g., `2026`). |
| `0x0424` | 4 B | `uint32_le` | **Start Month** | Month of recording start (`1` – `12`). |
| `0x0428` | 4 B | `uint32_le` | **Start Day** | Day of recording start (`1` – `31`). |
| `0x042C` | 4 B | `uint32_le` | **Start Hour** | Hour of recording start (`0` – `23`, 24-hour format). |
| `0x0430` | 4 B | `uint32_le` | **Start Minute** | Minute of recording start (`0` – `59`). |
| `0x0434` | 4 B | `uint32_le` | **Start Second** | Second of recording start (`0` – `59`). |
| `0x0438` | 4 B | `uint32_le` | **Sample Count ($N$)** | Total number of 1-second sample records ($1\text{ Hz}$). |

---

## 4. Payload Specification (Starting at Offset `0x043C`)

Each record represents 1 second of continuous measurement. Each record is exactly 2 bytes:

| Byte Offset | Type | Field Name | Range / Meaning | Sentinel / Invalid Value |
| :--- | :--- | :--- | :--- | :--- |
| $+0$ | `uint8` | **SpO2** | $1 - 100\%$ | `0x7F` (`127`) or `0x00` = Invalid / Probe-Out / Disconnected |
| $+1$ | `uint8` | **Heart Rate** | $1 - 250\text{ bpm}$ | `0xFF` (`255`) or `0x00` = Invalid / Probe-Out / Disconnected |

### Sentinel & Probe-Out Values
- The official Windows application `SpO2.exe` writes `[0x7F, 0xFF]` (`127, 255`) when the sensor probe is detached or signal is lost.
- Any values where $\text{SpO}_2 > 100$ or $\text{Pulse Rate} > 250$ (or equal to $0$) are treated as **probe-out / invalid** by decoders.

---

## 5. Software & Tooling Compatibility

1. **Contec SpO2 Assistant (Windows)**:
   - File dialog filter: `*.SpO2` (`.SpO2(Saves the complete data and can be opened with the current software only)`).
   - Expected default path: `%USERPROFILE%\AppData\Local\VirtualStore\Program Files (x86)\SpO2\Data\`.
   - Validates `magic == 0x358` (856) and parses start date/time block at offset `0x0420`.

2. **OSCAR (Open Source CPAP Analysis Reporter)**:
   - Imports `.SpO2` files via the **Oximetry Import Wizard**.
   - Aligns 1 Hz oximetry data against CPAP flow and pressure data using the header timestamp.
   - **Verified against OSCAR's actual source** (2026-10-19,
     `gitlab.com/CPAPreporter/oscar-code`, `oscar/SleepLib/loader_plugins/cms50f37_loader.cpp`,
     `CMS50F37Loader::readSpoRFile`) rather than taken on description alone. OSCAR's own project
     explicitly states PO-400 compatibility: "other companies, such as Pulox, simply rebadge
     Contec CMS50's under new names, such as the Pulox PO-200, PO-300, PO-400. These should also
     work" (`oximeterimport.cpp`). What its reader actually does, byte for byte:
     - Reads a `uint16` at `0x0000` and treats it as a **dynamic skip-to offset**, not a validated
       magic constant -- it never checks the value equals `856`, it just jumps there. This file's
       own value of `856` (`0x358`) works by construction, but OSCAR imposes no format-ID check
       of its own, so this field's role as a fixed "magic" is this project's own convention
       (matched by `SpO2.exe`'s validation at `0x4E2277`), not something OSCAR verifies.
     - Checks exactly one byte, `data[0x358] == 1`, then blindly skips 200 more bytes
       (`0x358` to `0x0420`) without reading or validating anything inside -- including the
       claimed `"BLE\0"` tag at `0x0360`. That tag's presence is unverified by OSCAR; it may
       still be accurate from other analysis, but OSCAR gives no independent confirmation of it.
     - Reads year/month/day/hour/minute/second as six consecutive `uint32`s starting at `0x0420`,
       then the sample count as a `uint32` at `0x0438` -- both **confirmed to match this
       document's layout exactly**.
     - Does **not** hardcode 2 bytes per record. It derives `bytes_per_record = remainder /
       samples` from the actual file size, and explicitly anticipates a 4-byte variant for some
       devices ("CMS50I .spo2 data have 4 digits, a 16bit, followed by spo2 then pulse"). This
       file's own writer (`fiedle400/export.py`) always emits exactly 2 bytes/record, so this
       doesn't affect `fiedle400`'s own output, but it means OSCAR's `.spo2` support is broader
       than a fixed 2-byte record.
   - **Two real discrepancies found, affecting how `fiedle400`'s own records are recognized:**
     - **Sentinel check is an AND, not independent per-field.** OSCAR only treats a record as
       probe-out when `SpO2 byte == 0x7F` **and** `Pulse byte == 0xFF` simultaneously
       (`if ((o2 == 0x7f) && (pr == 0xff))`) -- it does not treat either sentinel alone as
       sufficient. This document's §4 describes each field's sentinel independently. If
       `fiedle400` ever wrote a record where only one channel decoded as invalid (SpO2 = `0x7F`
       but Pulse = a real, valid value, or vice versa), OSCAR would import the invalid channel's
       sentinel as a literal, impossible reading (e.g. a `127%` SpO2 point on the chart) instead
       of blanking it. **Fixed (T-004, 2026-10-20):** `fiedle400/export.py`'s `build_spo2_binary`
       now writes the sentinel pair `(0x7F, 0xFF)` for both bytes whenever *either* channel is
       invalid, never a mixed pair -- its own output always matches OSCAR's AND-check. The mixed
       state was confirmed reachable, not just a defensive hypothetical: `fiedle400/engine/device.py`'s
       block-pairing logic (`flush_block_buffers`) derives `is_probe_out` from whichever of the
       SpO2/pulse event pair is present, checking only that one event's own status -- so a record
       whose SpO2 channel decodes "ok" while its pulse channel decodes `None` with no prior
       `last_block_hr` to fall back on (e.g. the very first record of a session) reaches
       `export.py` as `spo2=<value>, heart_rate=None`, a genuinely mixed record, not merely one
       `export.py` could theoretically be handed.
     - **`0x00` is not a recognized sentinel in OSCAR's reader at all.** It is passed through
       literally as the value `0`; OSCAR has no special case for it. This document's §4 claiming
       `0x00` as an alternate sentinel for either field describes `fiedle400`'s/this spec's own
       convention, not something OSCAR's actual importer checks for.

3. **`fiedle400` CLI & Python Library**:
   - Native export support: `--format spo2` / `-f spo2` (default format).
   - File extension: `.spo2` or `.SpO2`.

---

## 6. Reference Implementation (Python)

### 6.1 Writer / Exporter

```python
import struct
from datetime import datetime
from typing import List, Optional, Tuple

HEADER_SIZE = 1084

def build_spo2_file(start_dt: datetime, samples: List[Tuple[Optional[int], Optional[int]]]) -> bytes:
    """Build a complete binary .SpO2 file.
    
    Args:
        start_dt: Recording start timestamp.
        samples: List of (spo2, heart_rate) tuples, 1 per second.
                 None indicates invalid / probe-out.
    Returns:
        bytes: Complete binary .SpO2 file content.
    """
    hdr = bytearray(HEADER_SIZE)
    # 0x0000: Magic (0x0358 = 856), 0x0004: Version (1)
    struct.pack_into("<II", hdr, 0x0000, 0x0358, 0x0001)
    # 0x0358: Channel flag (1)
    struct.pack_into("<I", hdr, 0x0358, 0x0001)
    # 0x0360: "BLE" UTF-16LE tag
    hdr[0x0360:0x0366] = b"B\x00L\x00E\x00"
    # 0x0420: Datetime block and sample count
    struct.pack_into(
        "<7I",
        hdr,
        0x0420,
        start_dt.year,
        start_dt.month,
        start_dt.day,
        start_dt.hour,
        start_dt.minute,
        start_dt.second,
        len(samples),
    )
    payload = bytearray(len(samples) * 2)
    for i, (spo2, hr) in enumerate(samples):
        # 127 (0x7F) and 255 (0xFF) are native sentinel values
        s_byte = spo2 if (spo2 is not None and 1 <= spo2 <= 100) else 127
        h_byte = hr if (hr is not None and 1 <= hr <= 250) else 255
        payload[i * 2] = s_byte
        payload[i * 2 + 1] = h_byte

    return bytes(hdr + payload)
```

### 6.2 Reader / Decoder

```python
def read_spo2_file(data: bytes) -> Tuple[datetime, List[dict]]:
    """Parse a .SpO2 binary file."""
    if len(data) < HEADER_SIZE:
        raise ValueError("Data smaller than header size (1084 bytes)")
    magic, ver = struct.unpack_from("<II", data, 0x0000)
    if magic != 0x0358:
        raise ValueError(f"Invalid magic: 0x{magic:08x} (expected 0x00000358)")
    
    y, m, d, H, M, S, count = struct.unpack_from("<7I", data, 0x0420)
    start_dt = datetime(y, m, d, H, M, S)
    payload = data[HEADER_SIZE:]
    
    records = []
    for i in range(min(count, len(payload) // 2)):
        s_val = payload[i * 2]
        h_val = payload[i * 2 + 1]
        is_valid = (1 <= s_val <= 100) and (1 <= h_val <= 250)
        records.append({
            "second": i,
            "spo2": s_val if is_valid else None,
            "heart_rate": h_val if is_valid else None,
            "valid": is_valid,
        })
    return start_dt, records
```

---

## 7. SpO2 Assistant Analysis Definitions (Reference Only)

Reference material from T-017 (2026-10-20). This section describes how the vendor's
SpO2 Assistant computes its report values. It is **not** a `fiedle400` feature spec;
`fiedle400` implements none of it (follow-up: T-018).

Sources: [M] = *SpO2 Assistant User Manual*, CONTEC, 2010-05-27
(`http://manual.pulseoximeter.org/SPO2_Assistant_Manual.pdf`), section given;
[X] = static disassembly of `archive/bruteforce/SpO2.exe` (gitignored local artifact),
virtual address given (image base `0x400000`). Anything not backed by one of these is
marked *inferred*.

### 7.1 Report values

| Report label | Definition | Source |
| :--- | :--- | :--- |
| Basal SpO2 (%) | "the average value of SpO2 total" -- the mean SpO2 of the recording, not a sleep or awake baseline. Whether excluded ranges and artifact samples are left out of the mean is *inferred* (likely, not verified). **T-019 real-run evidence (2026-10-20):** the probe's flat mean over all samples predicts 95.39 %, the real SpO2 Assistant reported 96.2 % -- a +0.8 pt difference consistent with event-affected ranges being excluded from the mean (not just artifact/sentinel samples), but not confirmed by disassembly. Still *inferred*, now with a real discrepancy pointing the same direction. | [M] §5.4.7.3 |
| Total Event | Number of SpO2 desaturation events (7.2). | [M] §5.4.7.3 |
| Index (1/hr) | "the event number per hour" (events / recording hours). | [M] §5.4.7.3 |
| Adjusted Index (1/hr) | Total Event divided by the "effective" time length instead of the total. | [M] §5.4.7.3 |
| Artifact (%) | Share of non-effective data: "that zero value area and excluding data area" (zero/invalid samples plus user-excluded ranges, see [M] §5.4.2 Exclude data). | [M] §5.4.7.3 |
| Avg. Low SpO2 (%) | "the average value of 'Minimum SpO2' for all SpO2 events" (mean of event nadirs). | [M] §5.4.7.3 |
| Time (min) <88% | Time below the desaturation criteria level; "88 is a desaturation criteria level (set in analysis parameter dialog box)". Default 88 % confirmed in code: a global at `0x6263cc` initialised to 88 in `.data`, read via `0x56027a`, written only by the Analysis Para dialog (`0x4fc007`, setter `0x56026b`), so it is not loaded from `config.ini`/`SpO2.ini` (*inferred* from no other writer). | [M] §5.4.7.3, [X] |

### 7.2 Desaturation event algorithm

**Parameters.** The analysis-parameter XML writer (`0x4fde76`-`0x4fdf2d`) emits
`<analy_para><spo2><drop/><min_time/><max_time/><oscillation/><max_avg/><criteria/></spo2><pulse><drop/><time/></pulse>`.
The detector is built at `0x532a43` (`call 0x533300`) with exactly these values:

| Parameter | Default | UI range | Meaning (from the code) | Source |
| :--- | :---: | :---: | :--- | :--- |
| `drop` (Percent Drop For Event) | 4 % | 1-20 | Minimum depth: start value minus nadir value. | [X] init `0x531e96`, `0x53215b`; ranges from exe strings |
| `min_time` (Minimum Event Duration) | 10 s | 1-180 | Minimum descent duration, and the maximum gap bridged when merging (below). | [X] same |
| `max_time` | 180 s | fixed | Maximum descent duration. | [X] `push 0xb4` at `0x532a55` |
| `max_avg` | 2 | fixed | Average fall rate must be **below** 2 %/sample; steeper drops are rejected. | [X] `0x535e42` |
| `oscillation` | 1 | fixed | Rebound tolerance in % for merging partial descents. | [X] `0x53580e` |
| valid range | 0..100 | fixed | Samples outside it break an event (e.g. the `0x7F` probe-out sentinel). | [X] `0x535469`, `0x535f60` |
| Pulse change / time | 6 bpm / 8 s | 2-20 bpm | Pulse-rate event parameters; that detector was not decoded. | [X] init routines |

**Detection** (`0x535430`, per SpO2 sample; `.SpO2` data is 1 Hz, so a sample is a second):

1. A sample outside 0..100 ends the current candidate.
2. A rise (`s[i] > s[i-1]`) ends the current candidate.
3. A fall (`s[i] < s[i-1]`) starts a candidate at `i-1` if none is open and `s[i-1]` is
   between 1 and 99; otherwise it extends the open candidate to `i`. A flat sample extends
   an open candidate.
4. So the **baseline is the last sample before the fall starts (the local peak)**, not a
   moving average or a rolling baseline. A candidate records start index/value, nadir
   index/value, `duration = nadir_idx - start_idx` and `depth = start_val - nadir_val`
   (`0x535d60`).

**Merging** (`0x535710`, active because `oscillation` = 1). Consecutive candidates are joined
when the next one starts at most `oscillation` (1 %) above where the current one ended, ends
lower and starts lower than the current one, and begins at most `min_time` samples after the
current one's nadir. The joined event keeps the first start and takes the later nadir. This
turns a staircase descent with small rebounds into one event.

**Acceptance** (`0x535df0` + `0x535f60`). An event counts when all hold:
`depth >= drop`, `min_time <= duration <= max_time`, `depth / duration < max_avg`
(integer division), and every sample from start to nadir is inside 0..100.

Not determined: whether user-excluded ranges are removed from the series before detection
(*inferred*: probably, since the manual counts them as non-effective time), and how the
pulse-rate events are detected. Note that "duration" is the **descent time to the nadir**,
not the time spent below the start value, which differs from AASM-style scoring.

Validation: `scripts/make_desat_probe.py` writes a synthetic probe recording with the
predicted report values; T-019 runs it through the real SpO2 Assistant. **Run 1 of 3
done (2026-10-20, default parameters drop=4/min_time=10/criteria=88):** Total Event,
Index, Adjusted Index, Avg. Low SpO2, Time <88%, Minimum SpO2 and Artifact % all
matched; Basal SpO2 differed by +0.8 pts (see §7.1). The two previously-undecoded
report fields `Ereignis<88%` and `Durchschn. niedrige SpO2<88%` were confirmed from
the live UI's German labels and match exactly. Still pending: reruns at drop=3 and
min_time=8 (full details: `tickets/open/T-019-validate-desat-algorithm-in-spo2-assistant.md`).
Until all three runs are done this section remains a hypothesis, now partially
corroborated rather than purely static.
