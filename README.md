# Pulsox PO-400 CLI Tool (`po400`)

A lightweight Python Command-Line Interface (CLI) to communicate with the **Pulsox PO-400** (and compatible Contec CMS-50 series) pulse oximeter over USB HID on Linux.

For detailed hardware & protocol specifications, see [DESIGN.md](file:///home/mik/Documents/Bastel/2023-/po400/DESIGN.md).

## Features
- **Zero-Dependency Core**: Communicates natively with `/dev/hidraw*` device nodes without relying on buggy libusb C-wrappers.
- **Device Info Reader (`po400 info`)**: Auto-detects connected PO-400 USB HID devices (`VID 0x28E9`, `PID 0x028A`), queries hardware model, raw sysfs parameters, firmware version, serial number (`50F`), user profile string (`user`), and storage geometry (`112B Sub-chunk Payload, 4KB Address Block`).
- **Real-Time Clock Read & Write (`po400 read-time` / `po400 set-time`)**: Reads hardware RTC clock (`0x82`) and synchronizes device RTC clock (`0x83`) with PC system time.
- **Session Index Lister (`po400 sessions`)**: Queries session metadata index table (`0x9C` / `0xEC`), listing all recorded offline sessions in device memory.
- **Session Data Downloader (`po400 download`)**: Extracts stored recordings from device memory into CSV or JSON format in a 100% non-destructive manner.
- **Device Memory Clear (`po400 clear`)**: Deletes stored recording sessions from device flash memory (`0xAA`).

---

## Installation & Setup

### 1. Permissions Setup (Linux)
On Linux, raw USB HID devices require read/write access. You can grant access permanently by adding a udev rule:

```bash
echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="28e9", ATTRS{idProduct}=="028a", MODE="0666"' | sudo tee /etc/udev/rules.d/99-pulsox.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Alternatively, grant temporary access:
```bash
sudo chmod 666 /dev/hidraw*
```

### 2. Package Installation & Running Commands

Run commands directly without installing (`pip install` is not required):
```bash
# 1. Read hardware information, serial (50F), and storage geometry
python3 -m po400.cli info

# 2. Read & set device Real-Time Clock (RTC)
python3 -m po400.cli read-time
python3 -m po400.cli set-time
python3 -m po400.cli set-time "2026-09-03 09:45:30"

# 3. List all stored recording sessions on device
python3 -m po400.cli sessions

# 4. Download ALL stored recording sessions (Default)
python3 -m po400.cli download -o all_sessions.csv

# 5. Download a specific session (e.g. Session #1)
python3 -m po400.cli download -s 1 -o session_1.csv

# 6. Clear/delete ALL stored recording sessions from device flash memory
python3 -m po400.cli clear -y
```

---

## Usage Examples

You can run commands using `po400 <command>` (if installed) or `python3 -m po400.cli <command>` (without installing):

### 1. Read Device Information
```bash
po400 info
# or
python3 -m po400.cli info
```

### 2. Extract Saved Recording Sessions to CSV
```bash
po400 download -o overnight_recording.csv
# or
python3 -m po400.cli download -o overnight_recording.csv
```

### 3. Extract Recording Sessions to JSON
```bash
po400 download -o overnight_recording.json -f json
# or
python3 -m po400.cli download -o overnight_recording.json -f json
```

---

## Documentation & Protocol References

- **[DESIGN.md](file:///home/mik/Documents/Bastel/2023-/po400/DESIGN.md)**: Full technical specification, USB HID framing, command codes, and memory architecture.
- **[PROTOCOL.md](file:///home/mik/Documents/Bastel/2023-/po400/PROTOCOL.md)**: Bit-accurate protocol specification and packet byte maps.

---

## Running Unit Tests
```bash
python3 -m unittest discover tests
```
