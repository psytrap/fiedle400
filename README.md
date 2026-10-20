# Pulsox PO-400 CLI Tool (`fiedle400`)

A lightweight Python Command-Line Interface (CLI) to communicate with the **Pulsox PO-400** (and compatible Contec CMS-50 series) pulse oximeter over USB HID. Runs on **Windows and Linux**, verified against real hardware on both (macOS support is present but not yet verified).

> **Status: beta.** Verified against real hardware, including a real finger-on-probe session with a plausible SpO2/heart-rate trace. See [RELEASE_PLAN.md](RELEASE_PLAN.md).

For the code architecture see [DESIGN.md](DESIGN.md); for the byte-level protocol see [PROTOCOL.md](PROTOCOL.md).

---

## Features

**Get your data off the device -- the main reason this tool exists**
- **`fiedle400 download`**: extracts stored recordings and saves them, by default as a **self-contained HTML page** (`.html`: chart, desaturation and pulse-rate event report with adjustable parameters, print button; open it in any browser, now or later, no install). `-f spo2` (SpO2 Assistant / OSCAR), `-f csv` and `-f json` are still available. Since 0.4.26 no `.spo2` is written unless you ask for it; `-o name.spo2` (or any `.html`/`.csv`/`.json`) also picks the format by extension. The command never opens a browser. Non-destructive: device memory is untouched unless you separately choose to clear it.
- **`fiedle400 view [FILE]`**: shows a `.spo2`/`.csv`/`.json` recording already on disk in the HTML viewer, without leaving a file behind (a temporary page is opened in your default browser and removed). Without FILE it takes the latest recording in the current directory, then in the working directory. `--convert [-o OUT]` instead writes the page as `<recording>.html` (or OUT) and does not open a browser. Standard library only. (This replaces the old `plot` command, which needed matplotlib and drew a PNG; see RELEASE_PLAN B1b and T-006.)
- **Interactive wizard (`fiedle400`, no arguments)**: the guided way to do both of the above in one pass -- a menu to inspect device status, download sessions, and manage device memory. The download flow asks for an output format (`html` (default) / `spo2` / `csv` / `json`) as its own prompt before the filename. After saving an `html` page it asks "Open it in your browser now? [y/N]" (default no); for `spo2` it offers to open a temporary viewer page. The wizard header and `--help` show the project page.

**Driver**
- **Dual-backend**: Linux defaults to `hidraw` -- 100% standard library, zero external dependencies (`pip install` is NOT required). Windows and macOS default to `hid` (`import hid`, pulled in automatically on those platforms). Pass `--backend hid` on Linux to develop and test the cross-platform path locally.

**Everyday use**
- **`fiedle400 selftest`**: a one-command, read-only hardware check (detection, connect, handshake, clock, sessions) against the real device -- no env var needed, unlike the test suite's opt-in live tests; running this command is itself the signal that a check is wanted. Automatically probes every backend this platform supports (e.g. both `hidraw` and `hid` on Linux) in one run; only the primary backend's result affects the exit code, so a known-flaky secondary backend never masks an otherwise-healthy device.
- **`fiedle400 info`**: auto-detects the connected PO-400 (`VID 0x28E9`, `PID 0x028A`) and reports its hardware model, firmware version, serial number, user profile, and storage geometry -- printing "not reported by the device" rather than guessing at whatever it doesn't actually answer (most likely a device firmware limitation, not something more reverse-engineering would fix -- see `PROTOCOL.md` §3.3).
- **`fiedle400 sessions`**: lists every recorded session in device memory from the stored index table.
- **`fiedle400 clear`**: deletes stored sessions from device flash memory -- the only destructive command, confirmed by default.

**Clock**
- **`fiedle400 read-time` / `fiedle400 set-time`**: sends the clock read (`0x82`) / set (`0x83`) commands. The PO-400's clock reply never varies, so `read-time` shows it raw and says the clock isn't reported rather than decoding it into a fabricated date; `set-time` is unverified against real hardware. Stored sessions carry their own correct timestamps regardless.

**Other**
- **`fiedle400 config`**: shows or changes where recordings are saved.
- **`fiedle400 detect`**: a live, low-level view of the raw USB HID packet stream as the device sends it -- a debugging tool, not needed for normal use.

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

- Python 3.11+
- `hid` library: `pip install hid` (CI and the release binary use the `hidapi` package, which also provides `import hid`)

```cmd
REM Windows batch wrapper
fiedle400.bat --help
fiedle400.bat info

REM Or via the Python module directly
python -m fiedle400 --help
python -m fiedle400 info
```

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

#### Uninstall on Linux

| What | How to remove it |
|---|---|
| Standalone binary and desktop launcher | `./install.sh --uninstall` (from the extracted release folder). Removes `~/.local/bin/fiedle400` and `~/.local/share/applications/fiedle400.desktop`. |
| Saved settings | The same command asks, for each, before removing `~/.config/fiedle400/` (and `~/.config/po400/`, if you used the tool before it was renamed). Default is to keep them. Without the script: `rm -rf ~/.config/fiedle400 ~/.config/po400`. |
| Device-access (udev) rules | Needs root, so the script only prints it: `sudo rm -f /etc/udev/rules.d/99-pulsox*.rules && sudo udevadm control --reload-rules && sudo udevadm trigger` |
| Installed with pip or pipx | `pip uninstall fiedle400` or `pipx uninstall fiedle400`. Settings and udev rules as above. |
| Recordings | Never removed. They are in your working folder (`fiedle400 config` shows it; the launcher uses `~/Documents/fiedle400`). |

(`$XDG_CONFIG_HOME` replaces `~/.config` in the settings paths if you set it.)

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

## Driver Backend Selection

You can explicitly choose the driver backend via the `--backend` (`--driver`) flag:

| Backend | Description | Default On | Dependencies |
|---|---|---|---|
| `hidraw` | Linux kernel direct `/dev/hidraw*` interface | **Linux** | Standard Library only (0 dependencies) |
| `hid` | Cross-platform driver via `import hid` | **Windows, macOS** | `pip install hid` |

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

# 1b. Watch the live stream (decoded packets)
fiedle400 detect

# 2. Read & synchronize device Real-Time Clock (RTC)
fiedle400 read-time
fiedle400 set-time

# 3. List all stored recording sessions
fiedle400 sessions

# 4. Download all sessions (default: an HTML viewer page you can open later)
fiedle400 download                            # fiedle400_all_sessions_<timestamp>.html
fiedle400 download -f spo2 -o all_sessions.spo2   # Contec .SpO2 binary (SpO2 Assistant / OSCAR)

# 4b. Choose where recordings go
fiedle400 config --workdir ~/Recordings          # stored setting (asked once on first interactive run)
fiedle400 download --workdir /tmp/run1           # this run only, not saved
FIEDLE400_WORKDIR=/tmp/run1 fiedle400 download       # same, for scripts and CI
# Precedence: -o > --workdir > FIEDLE400_WORKDIR > stored setting > current directory

# 5. Download a specific session to CSV or JSON
fiedle400 download -s 1 -o session_1.csv -f csv
fiedle400 download -s 1 -o session_1.json -f json

# 6. Look at a recording that is already on disk
fiedle400 view                           # latest recording in the current directory (then the working directory)
fiedle400 view session_1.spo2            # explicit file (.spo2, .csv, or .json); opens a temporary page
fiedle400 view session_1.spo2 --convert  # write session_1.html next to it instead, open nothing

# 7. Format / delete stored recording sessions from device flash memory
fiedle400 clear -y
```

---

## Running Unit Tests

Run the complete test suite (all tests use mocks and require 0 external dependencies):
```bash
python3 -m unittest discover -s tests
```
The suite must give the same result on any machine: it does not touch real hardware, the real
`/dev` or `/sys`, your saved settings, or `FIEDLE400_*` variables.

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
- **[DESIGN.md](DESIGN.md)**: Code architecture, module map, download flow, test layout.
- **[AGENTS.md](AGENTS.md)**: Rules for contributors, human or AI: commands, patch workflow, invariants.
- **[PROTOCOL.md](PROTOCOL.md)**: Bit-accurate protocol specification and packet byte maps.
- **[PACKAGING.md](PACKAGING.md)**: How the binaries, the Windows installer and the Linux tarball are built.
- **[RELEASE_PLAN.md](RELEASE_PLAN.md)**: Release gates, version-bump strategy, open findings.
