# Pulsox PO-400 CLI Tool (`fiedle400`)

A lightweight Python Command-Line Interface (CLI) to communicate with the **Pulsox PO-400** (and compatible Contec CMS-50 series) pulse oximeter over USB HID.

For detailed hardware & protocol specifications, see [DESIGN.md](DESIGN.md).

> **Renamed from `po400`.** The tool is now `fiedle400`; the device is still the PO-400. Saved settings are copied over on first run, and the old `PO400_*` environment variables still work.

---

## Features
- **Dual-Backend Driver**:
  - **Linux Default (`hidraw`)**: 100% standard library Python. Communicates directly with `/dev/hidraw*` device nodes with **zero external dependencies** (`pip install` is NOT required).
  - **Windows & macOS Default (`hid`)**: Cross-platform driver via `import hid` library (automatically included as a dependency when installing on Windows or macOS).
  - **Switchable**: Pass `--backend hid` on Linux to develop and test cross-platform logic locally.
- **Interactive Wizard (`fiedle400`)**: Running without arguments opens a guided menu to inspect device status, download session recordings, and manage device memory.
- **Device Info Reader (`fiedle400 info`)**: Auto-detects connected PO-400 USB HID devices (`VID 0x28E9`, `PID 0x028A`), queries the hardware model descriptor (e.g. `50F`), firmware version, serial number, user profile string, and storage geometry -- printing "not reported by the device" rather than a guess for whatever the device does not actually answer.
- **Real-Time Clock Read & Write (`fiedle400 read-time` / `fiedle400 set-time`)**: Reads hardware RTC clock (`0x82`) and synchronizes device RTC clock (`0x83`) with PC system time.
- **Session Index Lister (`fiedle400 sessions`)**: Queries session metadata index table (`0x9C` / `0xEC`), listing all recorded offline sessions in device memory.
- **Session Data Downloader (`fiedle400 download`)**: Extracts stored recordings from device memory into CSV or JSON format in a 100% non-destructive manner.
- **Device Memory Clear (`fiedle400 clear`)**: Deletes stored recording sessions from device flash memory (`0xAA`).

---

## Running on Linux

### 1. Install the standalone binary

Download `fiedle400-linux-x64.tar.gz` from the [GitHub Release](https://github.com/psytrap/fiedle400/releases), then:

```bash
tar xzf fiedle400-linux-x64.tar.gz
./install.sh            # installs to ~/.local/bin, no root needed
sudo ./fiedle400_setup-udev.sh   # one-time device-access setup, needs root
fiedle400 selftest      # verify: detection, connect, handshake, RTC, sessions
```

`install.sh` never touches anything outside your home directory and never
invokes `sudo` itself. `fiedle400_setup-udev.sh` is the opposite -- small,
standalone, and dedicated only to writing the udev rules the PO-400 needs for
non-root HID access, worth reading top to bottom before running it as root
(see `packaging/linux/`). `fiedle400 selftest` likewise never invokes `sudo`;
if it reports the device as "found but not readable/writable", it names that
script as the fix rather than trying to elevate on its own.

Uninstall with `./install.sh --uninstall` (removes the binary; the udev rules
stay, since removing those also needs root -- the script's own output tells
you the two commands for that).

#### Running from source instead

No external libraries or `pip install` required for the default `hidraw`
backend:
```bash
python3 -m fiedle400            # interactive wizard
python3 -m fiedle400 info
python3 -m fiedle400 sessions
python3 -m fiedle400 download -o recording.csv
```
Device access still needs the udev rules above -- run
`packaging/linux/fiedle400_setup-udev.sh` from a checkout the same way.

#### The `hid` (libusb) backend, for cross-platform testing on Linux

`--backend hid` is only needed if you are developing the cross-platform driver
itself; `hidraw` (the default) is what real Linux users should use.
`fiedle400_setup-udev.sh` installs both rules, so nothing extra is needed to
try it -- but be aware it is known to be unreliable on at least one Linux
machine (RELEASE_PLAN.md, finding T8): it connects, but the unlock handshake
and session query can get no useful reply where `hidraw` works perfectly
against the same device. Confirmed not to be a timing issue (polled a full
second with no change); root cause not yet found.

If you do try it: the installed `hid` module's backend matters. When it is
built against **libusb** rather than hidraw, it opens the raw USB node
(`/dev/bus/usb/...`) instead of `/dev/hidraw*`, and it **detaches the kernel
`usbhid` driver** while it holds the device, so `/dev/hidraw*` disappears for
the duration and takes a few tens of milliseconds to reappear after close.
Code that switches from `hid` to `hidraw` must wait for the node to return;
see `wait_for_hidraw_reattach()` in `tests/test_device_live.py`. To check which
backend your `hid` module uses, look at the path it reports -- `/dev/hidraw*`
means hidraw, a bus path like `1-7.4.4:1.0` means libusb:
```bash
python3 -c "import hid; print(hid.enumerate(0x28E9, 0x028A)[0]['path'])"
```

---

## Running on Windows

### 1. Install the standalone binary

Download `fiedle400-setup.exe` from the [GitHub Release](https://github.com/psytrap/fiedle400/releases) and run it --
no admin rights needed, installs per-user to `%LOCALAPPDATA%\Programs\fiedle400`.
Launch it from the Start Menu entry (opens the interactive wizard directly;
there is no console to type into) or the Explorer right-click "Open fiedle400
here" entry. Verified on Windows 8.1 and newer with a real device attached.

Device access needs no setup on Windows: the PO-400 binds to the stock HID
class driver automatically (no Zadig, no manual driver step).

#### Running from source instead

- Python 3.8+
- `hid` library: `pip install hid`

```cmd
REM Windows batch wrapper
fiedle400.bat --help
fiedle400.bat info

REM Or via the Python module directly
python -m fiedle400 --help
python -m fiedle400 info
```

---

## Driver Backend Selection

You can explicitly choose the driver backend via the `--backend` (`--driver`) flag:

| Backend | Description | Default On | Dependencies |
|---|---|---|---|
| `hidraw` | Linux kernel direct `/dev/hidraw*` interface | **Linux** | Standard Library only (0 dependencies) |
| `hid` | Cross-platform driver via `import hid` | **Windows** | `pip install hid` |

```bash
# Force hidraw (Linux default):
fiedle400 --backend hidraw info

# Force hid (Windows default, or for testing on Linux):
fiedle400 --backend hid info
```

---

## Usage Examples

```bash
# 1. Read device information
fiedle400 info

# 2. Read & synchronize device Real-Time Clock (RTC)
fiedle400 read-time
fiedle400 set-time

# 3. List all stored recording sessions
fiedle400 sessions

# 4. Download all sessions (defaults to Contec .SpO2 binary format)
fiedle400 download -o all_sessions.spo2

# 4b. Choose where recordings go
fiedle400 config --workdir ~/Recordings          # stored setting (asked once on first interactive run)
fiedle400 download --workdir /tmp/run1           # this run only, not saved
FIEDLE400_WORKDIR=/tmp/run1 fiedle400 download       # same, for scripts and CI
# Precedence: -o > --workdir > FIEDLE400_WORKDIR > stored setting > current directory

# 5. Download a specific session to CSV or JSON
fiedle400 download -s 1 -o session_1.csv -f csv
fiedle400 download -s 1 -o session_1.json -f json

# 6. Generate high-resolution PNG plot of session
fiedle400 plot                           # Automatically plots latest recording in output/
fiedle400 plot output/session_1.spo2     # Explicit recording file (.spo2, .csv, or .json)

# 7. Format / delete stored recording sessions from device flash memory
fiedle400 clear -y
```

---

## Running Unit Tests

Run the complete test suite (all tests use mocks and require 0 external dependencies):
```bash
python3 -m unittest discover tests
```

The hardware tests in `tests/test_device_live.py` are opt-in, so the default run gives
the same result whether or not a device is attached. With a PO-400 plugged in:
```bash
FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live -v
```
With `FIEDLE400_LIVE=1` and no reachable device, the suite fails instead of skipping.
Concurrent live runs are serialised through a lock file (`fiedle400-live-tests.lock` in the
temp directory), because two processes opening the oximeter at once collide.

### Simulated hardware (Linux)

`tests/test_hwsim_linux.py` runs the real hidraw backend, sysfs scan, engine, detector, export and
CLI against a simulated PO-400 (`tests/hwsim.py`) that replays device bytes recorded in
`analysis/bum400_20260906_100516.pcap`. It needs no device and runs in the normal suite. Commands
the recording does not cover get no reply, and destructive commands are refused and logged.
`tests/test_hwsim_realtrace.py` does the same with a recording of the CLI's own traffic on a real
device (`tests/fixtures/cli-exchange.trace.json`), where every command the CLI sends has a recorded
answer. To
extend the recording with the CLI's own traffic from a real device (read-only; it contains the
recorded measurements, so review it before sharing):
```bash
python3 tests/capture_tools/record_exchange.py -o cli-exchange.trace.json          # info, sessions, download
python3 tests/capture_tools/record_exchange.py --no-download -o info.trace.json    # no measurements
# open questions (read-only): firmware query 80 00, and SpO2 reads at other sample offsets
python3 tests/capture_tools/record_exchange.py --no-download --probe-firmware --probe-offsets 0,1,2,50,107,214,215,300 -o probe.trace.json
```

---

## Documentation & Protocol References

- **[SPO2_FORMAT.md](SPO2_FORMAT.md)**: Full binary format specification for Contec / Pulsox `.SpO2` files.
- **[DESIGN.md](DESIGN.md)**: Full technical specification, USB HID framing, command codes, and memory architecture.
- **[PROTOCOL.md](PROTOCOL.md)**: Bit-accurate protocol specification and packet byte maps.
- **[PACKAGING.md](PACKAGING.md)**: Distribution and installer design specifications.
