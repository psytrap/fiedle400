# Technical Specification & Design Document
## Pulsox PO-400 USB HID Interface & CLI Tool

---

## 1. System Overview

The **Pulsox PO-400** (marketed as Pulox PO-400 / Contec CMS-50 series derivative) is a prosumer medical pulse oximeter designed for SpO2 (blood oxygen saturation) and Heart Rate (PR) data storage and session analysis.

Unlike earlier serial-over-UART models, this hardware variant utilizes a native **GigaDevice USB Human Interface Device (HID)** controller (`Vendor ID: 0x28E9`, `Product ID: 0x028A`) communicating over raw `/dev/hidraw*` endpoints on Linux systems.

```
+------------------+         USB HID Reports (64-byte)        +-------------------+
|                  |  <====================================>  |                   |
| Pulsox PO-400    |                                          | Linux System      |
| Pulse Oximeter   |  [0x7D, 0x81, CMD, ...] -> (TX)          | (/dev/hidraw*)    |
| (VID: 0x28E9)    |  <- [0xF0, 0x70, ...] / Data (RX)        |                   |
| (PID: 0x028A)    |                                          |                   |
+------------------+                                          +---------+---------+
                                                                        |
                                                                        v
                                                              +-------------------+
                                                              | po400 CLI Tool    |
                                                              |  - scan           |
                                                              |  - sessions       |
                                                              |  - download       |
                                                              +-------------------+
```

---

## 2. Hardware & Interface Specification

### USB Descriptors
- **Vendor ID (VID)**: `0x28E9` (GigaDevice Semiconductor)
- **Product ID (PID)**: `0x028A` (Pulse Oximeter HID)
- **Class**: USB HID (Human Interface Device v1.11)
- **Endpoint Types**: Interrupt IN / Interrupt OUT
- **Linux Device Node**: `/dev/hidrawN` (automatically assigned by `hid-generic` driver)

### Hardware Identification & Verification (`0x28E9:0x028A`)

The assignment of `USB VID 0x28E9, PID 0x028A` to the **Pulsox PO-400 / Contec CMS-60D v2** is established through three empirical verification vectors and online registry sources:

1. **Kernel USB Descriptor Product String (`sysfs`)**:
   - Querying `/sys/class/hidraw/hidrawN/device/uevent` returns:
     ```text
     HID_ID=0003:000028E9:0000028A
     HID_NAME=GigaDevice Semiconductor Pulse Oximeter
     ```
   - `0x28E9` is the registered USB-IF Vendor ID for **GigaDevice Semiconductor Inc.**, the microcontroller chipmaker inside the PO-400.

2. **Official Vendor Installer INF Mapping (`SpO2_Assistant_v3_Setup.exe`)**:
   - The vendor setup package (`SpO2_Assistant_v3_Setup.exe`) contains driver configuration `hid_device.inf`, explicitly mapping the PO-400 device name:
     ```inf
     [DeviceList]
     %PO400.DeviceDesc% = USB_Install, USB\VID_28E9&PID_028A
     ```

3. **Empirical USB Hotplug & Kernel Sysfs Strings**:
   - Querying sysfs device parameters (`/sys/bus/usb/devices/1-7.4.4/manufacturer` and `/sys/bus/usb/devices/1-7.4.4/product`) returns raw text strings:
     ```text
     usb 1-7.4.4: Manufacturer: GigaDevice
     usb 1-7.4.4: Product: Pulse Oximeter
     ```
   - Dynamically plugging/unplugging the PO-400 USB cable logs kernel events:
     `usb 1-7.4.4: New USB device found, idVendor=28e9, idProduct=028a, bcdDevice= 2.07`

### Online References & External Sources

- **USB-IF Vendor ID Database**: [GigaDevice Semiconductor Vendor ID 0x28E9](https://www.usb.org/developers)
- **Contec / Pulox CMS Series Hardware Engineering**: [atbrask/CMS50Dplus Reverse Engineering Project](https://github.com/atbrask/CMS50Dplus)
- **Contec USB HID Communication Analysis**: [tranzoa.net CMS50/PO-400 HID Protocol Analysis](https://tranzoa.net)

### Linux Access & Permissions
Standard Linux installations restrict raw `/dev/hidraw*` access to `root` (`0600`).
Access is granted via a custom `udev` rule at `/etc/udev/rules.d/99-pulsox.rules`:

```text
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="28e9", ATTRS{idProduct}=="028a", MODE="0666"
```

---

## 3. Protocol & Packet Framing Specification

All communication between the host computer and the PO-400 takes place using **64-byte HID Reports**.

### 3.1 Host Output Command Reports (Host -> Device)
The host sends 64-byte reports formatted with a Contec header (`0x7D 0x81`) followed by the command byte and padding (`0x80`):

```text
Byte Offset  | Value / Meaning
-------------+-------------------------------------------------------------
[0]          | 0x7D (Header Byte 1)
[1]          | 0x81 (Header Byte 2)
[2]          | Command Code (e.g., 0xAF, 0xA1, 0xA6)
[3..N]       | Optional Arguments (e.g., [0x81, 0x81] for storage read)
[N..63]      | Padding Bytes (0x80)
```

#### Command Code Reference
| Command | Hex Code | Description | Response Header |
|---------|----------|-------------|-----------------|
| `UNLOCK_HANDSHAKE` | `0x7D 0xA7 / 0xA2` | Unlock state machine & negotiate storage session | `0xF0 0x70` ACK report |
| `PING` | `0xAF` | Keepalive ping / probe ACK | `0xF0 0x70` ACK report |
| `READ_RTC` | `0x82` | Query hardware Real-Time Clock | `0xF2` RTC BCD report |
| `SET_RTC` | `0x83` | Synchronize hardware Real-Time Clock | `0xF3 0x00 0x73` ACK report |
| `DEVICE_INFO` | `0x8E` | Query hardware serial number & user profile string | `0xFE` (Profile) & `0xF1` (Serial) |
| `USER_PROFILE` | `0x81` | Query User Profile ID 1 & serial number | `0xF1` Serial report |
| `INDEX_QUERY` | `0x9C` / `0x9B` | Query stored session metadata index table | `0xEC` Metadata report |
| `GEOMETRY_QUERY` | `0x9E` | Query Flash memory sub-chunk size & address block | `0x9E 0x70 0x04` Geometry report |
| `READ_STORAGE` | `0x9D 0x02 / 0x04` | Request recorded session stream | `0xEB` Data stream frames |
| `CLEAR_STORAGE` | `0xAA` / `0x9D 0x7F` | Reset session memory index table | `0xF0 0x70` ACK report |

---

### 3.2 Data Input Reports (Device -> Host)

Data is transmitted in 64-byte (or 18-byte) HID input reports containing sub-packets of **6-byte frame chunks**:

$$\text{Report} = \text{Chunk}_0 \parallel \text{Chunk}_1 \parallel \dots \parallel \text{Chunk}_k \quad (k = \lfloor \text{ReportLen} / 6 \rfloor)$$

#### 6-Byte Chunk Structure
```text
Byte Offset  | Field Name      | Description / Range
-------------+-----------------+---------------------------------------------
0            | Check Byte      | Sync & status byte (typically 0xF0)
1            | Update Flag     | 0 = PPG Wave update; 1 = HR & SpO2 update
2            | Status Flags    | Probe error, signal strength, pulse search
3            | Value 1         | If Update=0: PPG Wave (0-128)
             |                 | If Update=1: Heart Rate (BPM, 25-250)
4            | Value 2         | If Update=1: SpO2 Percentage (30-100%)
5            | Reserved        | Padding / Reserved byte (0x00)
```

#### Data Parsing Flowchart
```
                [Receive 6-byte Chunk]
                          |
            Is Check & Update Bytes Non-Zero?
                   /             \
                 NO               YES
                /                   \
        (Skip Idle Frame)    Check Update Flag
                                 /       \
                          Update == 0  Update == 1
                              /             \
               PPG_Wave = Value 1    Heart_Rate = Value 1
                                     SpO2       = Value 2
                              \             /
                         [Emit DataPoint Object]
```

---

## 4. Flash Memory Architecture (Sessions vs. Segments)

On **Hardware Version 2.0.0 (Contec CMS-60D v2 architecture)**, the internal flash memory organizes recorded data using a hierarchical **Session and Segment Layout**:

```text
+---------------------------------------------------------------------------------------------------+
| PO-400 FLASH MEMORY INDEX TABLE (0xA5 Query)                                                      |
|                                                                                                   |
|  +-----------------------------------+-----------------------------------+                        |
|  | SESSION #1 (e.g., Night 1 Sleep)    | SESSION #2 (e.g., Night 2 Sleep)  | ... up to Session #10 |
|  +-----------------------------------+-----------------------------------+                        |
+-------------------+-------------------------------------------------------------------------------+
                    |
                    v
    Divided into 512-Byte Flash Pages / Blocks
                    |
   +----------------+----------------+----------------+
   | SEGMENT 1      | SEGMENT 2      | SEGMENT 3      | ... up to Segment M
   | (Data chunk 1) | (Data chunk 2) | (Data chunk 3) |
   +----------------+----------------+----------------+
```

### Alignment Definitions

1. **Session (`session_id`, range `1..10`)**:
   - A **Session** represents one complete, continuous recording measurement (e.g., an overnight sleep study session from when `Record` was set to `ON` in the device menu until `OFF`).
   - The device flash memory holds up to **10 Session Slots** (`Session #1` through `Session #10`).

2. **Segment (`segment_id`, range `1..255`)**:
   - A **Segment** represents a 512-byte contiguous flash memory block inside a specific session.
   - Because single continuous recordings can be megabytes in size, flash memory splits large sessions into sequential **Segments** (`Segment 1`, `Segment 2`, ..., `Segment M`).

---

### Command Payload Alignment (`0xA6`)

When requesting data over USB HID, the parameters in the `0xA6` payload specify both the **Session ID** and **Segment ID**:

$$\text{Command Payload} = \text{\texttt{[0x7D, 0x81, 0xA6, Session\_ID, Segment\_ID, 0x80, ...]}}$$

- `0x7D 0x81 0xA6 0x01 0x01`: Retrieves **Segment 1** of **Session 1**.
- `0x7D 0x81 0xA6 0x01 0x02`: Retrieves **Segment 2** of **Session 1**.
- `0x7D 0x81 0xA6 0x02 0x01`: Retrieves **Segment 1** of **Session 2**.

The `po400 download` subcommand automatically steps through every **Segment** of every **Session** until all stored records are extracted into CSV/JSON.

---

## 5. CMS60D v2 Stored Data Transfer Protocol Specification

### 5.1 Initialization & Handshake Commands
Unlike legacy serial devices, the CMS60D v2 firmware requires explicit active polling and handshake initialization from the host before streaming session data:

- **Session Negotiation (`0xA2`)**: Host issues `0x7D 0x81 0xA2 0x80...` to initiate session negotiation and retrieve user descriptors.
- **Real-Time Request (`0xA1`)**: Host issues `0x7D 0x81 0xA1 0x80...` to trigger packet streaming.
- **Keep-Alive Ping (`0xAF`)**: Host re-sends `0x7D 0x81 0xAF 0x80...` every 1000–2000 ms to maintain active bus communication.

---

### 5.2 Stored Data Framing (3-Byte Sample Records)

Stored recordings are delivered in 3-byte sequential sample records:

$$\text{Sample Frame} = \text{\texttt{[Time\_Tick, SpO2\_Percentage, Pulse\_Rate\_BPM]}}$$

```text
Byte Offset  | Field Name          | Description / Range
-------------+---------------------+---------------------------------------------
0            | Second Tick / Sync  | Relative Time Offset; Bit 7 set ((byte & 0x80) != 0)
1            | SpO2 Percentage     | Blood Oxygen Saturation (0 - 100%)
2            | Pulse Rate (BPM)    | Heart Rate in BPM (0 - 254 BPM)
```

---

### 5.4 Ground-Truth Packet Capture Protocol (`pcap/bum400.pcapng`)

Dissection of the PCAPNG trace (`pcap/bum400.pcapng`) captured directly during an active PO-400 device download session revealed the exact 64-byte HID command framing:

#### Host OUT Command Layout (`0x9D`)
$$\text{Report} = [\text{\texttt{0x9D}}, \text{SubCmd}, \text{Block\_ID}, 0x01, \text{Session\_ID}, 0x00, 0x00, \text{Checksum}, 0x00 \dots]$$

- **Checksum**: Computed as `(sum(bytes 0..7)) & 0xFF`.
- **Session Init**: `0x9D 0x02 0x7F 0x7F 0x7F 0x00 0x00 0x1C`
- **Block Request**: `0x9D 0x04 [Block_ID] 0x01 [Session_ID] 0x00 0x00 [Checksum]`
- **Session Finalize**: `0x9D 0x7F 0x7F 0x7F 0x7F 0x00 0x00 0x19`

#### Device IN Response Layout (`0xEB` / `0xED`)
Device streams 64-byte HID input reports containing sub-chunks:

$$\text{Sub-Chunk} = [\text{\texttt{0xEB}}, \text{SubStatus}, \text{SubIndex}, \text{Pulse\_Rate\_BPM}, \text{Flags}, \text{SpO2\_Percentage}]$$

- **SpO2 Percentage**: `payload[5]` ($30..100$)
- **Heart Rate**: `payload[3]` ($30..250\text{ BPM}$)

---

## 6. Software Architecture

The Python software package (`po400/`) is designed with a zero-dependency architecture relying strictly on Linux native system calls (`os.open`, `os.read`, `os.write`).

```text
po400/
├── pyproject.toml         # Package definition & CLI executable entry point
├── README.md              # Installation and usage instructions
├── DESIGN.md              # Technical specification & architecture design
├── po400/
│   ├── __init__.py        # Package version
│   ├── hid_driver.py      # /sys/class/hidraw scanner & non-blocking I/O
│   ├── protocol.py        # Frame parser & command generator
│   └── cli.py             # argparse CLI entry point (scan, info, sessions, download, clear)
└── tests/
    ├── __init__.py
    └── test_protocol.py   # Unit tests for packet parsing & command building
```

### Module Responsibilities

1. **`po400.hid_driver`**:
   - Scans `/sys/class/hidraw/hidraw*/device/uevent` to locate device nodes matching `28E9:028A`.
   - Manages non-blocking file descriptors (`os.O_RDWR | os.O_NONBLOCK`).

2. **`po400.protocol`**:
   - Defines `DataPoint` dataclass.
   - Encapsulates `build_hid_command()` and `parse_hid_chunks()`.

3. **`po400.cli`**:
   - `scan` / `info`: Enumerates device nodes and reads hardware model provenance.
   - `sessions`: Lists stored recording sessions from device index table.
   - `download`: Extracts recorded data and exports to CSV or JSON formats.
   - `clear`: Executes 3-stage flash memory format and reset.

---

## 5. Output Data Schemas

### CSV Schema (`.csv`)
```csv
timestamp,spo2,heart_rate,ppg_wave,flags
2026-09-02T08:04:15.123456,98,72,85,16
2026-09-02T08:04:15.143456,98,72,88,16
```

### JSON Schema (`.json`)
```json
[
  {
    "timestamp": "2026-09-02T08:04:15.123456",
    "spo2": 98,
    "heart_rate": 72,
    "ppg_wave": 85,
    "flags": 16
  }
]
```

---

## 6. Open Discussion Points (Future GUI / Viewer Phase)

When revisiting Phase 2 (GUI Viewer), the following design points can be considered:

1. **GUI Technology Selection**:
   - **Tkinter + Matplotlib**: Built-in Python desktop UI for session graphing.
   - **Local Web App**: FastAPI + Chart.js web page (`po400 view session.csv`).
2. **Sleep Study Analytics**:
   - **ODI3 / ODI4 Calculation**: Oxygen Desaturation Index (number of SpO2 drops $\ge 3\%$ or $\ge 4\%$ per hour).
   - **Time Below Threshold**: Total duration spent below $90\%$ SpO2.
