"""USB-serial transport for Contec oximeters that are not HID (T-101).

SpO2 Assistant sends the PO-400's command frames unchanged over USB-serial at 115200 baud
(PROTOCOL.md §5), so a serial model needs only a transport, not a new protocol. This module
gives `SerialBackend` the same interface as the HID backends in `hid_driver.py`, so the
engine runs on it unchanged. Standard library only (the shipped binary has no dependencies):
termios on Linux/macOS, the Win32 COM API through ctypes on Windows.

Untested on real hardware: nobody on the project owns a serial model yet (T-102).
"""

import os
import sys
import time
from typing import List, Optional, Tuple

from .protocol.commands import build_hid_command, build_unlock_negotiate_handshake
from .protocol.hardware import SERIAL_USB_IDS

BAUD_RATE = 115200  # SpO2.exe's connect routine, PROTOCOL.md §5
REPORT_SIZE = 64
# A reply arrives as one burst (64 bytes take about 5.6 ms at 115200 baud). A gap this long
# ends a "report", so each reply starts at offset 0 like a HID report does.
QUIET_GAP_SEC = 0.01

PROBE_TIMEOUT_SEC = 0.3

# Module constant so tests can point it at a simulated tree (as hid_driver.SYSFS_HIDRAW_ROOT).
SYSFS_TTY_ROOT = "/sys/class/tty"


def unpad_report(report: bytes) -> bytes:
    """The command bytes of a 64-byte HID report, without its padding.

    HID reports are padded to 64 bytes (`0x80` after a `7D 81` frame, `0x00` after a bare
    one). A serial line has no reports, and the padding would reach the device as extra
    bytes (`0x80` is itself an opcode), so it is cut off. A bare command ends with its
    checksum (PROTOCOL.md §1.2), which may be `0x00`; that one is kept.
    """
    data = bytes(report)
    if data[:2] == b"\x7d\x81":
        return data.rstrip(b"\x80")
    end = len(data.rstrip(b"\x00"))
    if end == 0:
        return b""
    if end >= 2 and data[end - 1] == sum(data[:end - 1]) & 0x7F:
        return data[:end]
    if end < len(data) and sum(data[:end]) & 0x7F == 0:
        return data[:end + 1]  # the checksum itself is 0x00
    return data[:end]


def is_serial_path(path: Optional[str]) -> bool:
    """True for a path that names a serial port rather than a HID node."""
    if not path:
        return False
    p = str(path)
    if p.upper().startswith("COM") and p[3:].isdigit():
        return True
    base = os.path.basename(p)
    return base.startswith(("ttyUSB", "ttyACM", "cu.", "tty.usb"))


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except OSError:
        return None


def _linux_candidates() -> List[Tuple[str, str, str]]:
    found = []
    if not os.path.isdir(SYSFS_TTY_ROOT):
        return found
    wanted = {(f"{v:04X}", f"{p:04X}") for v, p in SERIAL_USB_IDS}
    for node in sorted(os.listdir(SYSFS_TTY_ROOT)):
        dev_link = os.path.join(SYSFS_TTY_ROOT, node, "device")
        if not os.path.exists(dev_link):
            continue
        curr = os.path.realpath(dev_link)
        for _ in range(6):  # walk up from the interface to the USB device
            vid = _read_text(os.path.join(curr, "idVendor"))
            pid = _read_text(os.path.join(curr, "idProduct"))
            if vid and pid:
                if (vid.upper(), pid.upper()) in wanted:
                    found.append((os.path.join("/dev", node), vid.upper(), pid.upper()))
                break
            curr = os.path.dirname(curr)
    return found


def _windows_present_ports(winreg) -> Optional[set]:
    """COM ports that exist right now (HARDWARE\\DEVICEMAP\\SERIALCOMM, the list SpO2.exe reads
    too), or None if it cannot be read. The USB Enum keys also remember unplugged devices."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return None
    ports, i = set(), 0
    while True:
        try:
            _name, value, _type = winreg.EnumValue(key, i)
        except OSError:
            break
        ports.add(str(value).upper())
        i += 1
    return ports


def _windows_candidates(winreg=None) -> List[Tuple[str, str, str]]:
    if winreg is None:
        import winreg  # noqa: F811  (Windows only)
    present = _windows_present_ports(winreg)
    found = []
    for vid, pid in SERIAL_USB_IDS:
        key_path = rf"SYSTEM\CurrentControlSet\Enum\USB\VID_{vid:04X}&PID_{pid:04X}"
        try:
            dev_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                instance = winreg.EnumKey(dev_key, i)
            except OSError:
                break
            i += 1
            try:
                params = winreg.OpenKey(dev_key, instance + r"\Device Parameters")
                port, _ = winreg.QueryValueEx(params, "PortName")
            except OSError:
                continue
            if port and (present is None or str(port).upper() in present):
                found.append((str(port), f"{vid:04X}", f"{pid:04X}"))
    return found


def find_serial_candidates() -> List[Tuple[str, str, str]]:
    """Serial ports whose USB ID is one SpO2 Assistant scans for: (port, vid_hex, pid_hex).

    Linux reads sysfs and Windows the registry. On macOS nothing is listed; pass the port
    with `--device /dev/cu.…` instead. A port listed on Windows may belong to a device that
    is not plugged in right now; opening it then fails with a clear error.
    """
    try:
        if sys.platform.startswith("linux"):
            return _linux_candidates()
        if sys.platform == "win32":
            return _windows_candidates()
    except Exception:
        pass
    return []


def find_model_frame(data: bytes) -> Optional[str]:
    """The model string of the first valid `0xF1` reply in `data`, or None.

    Valid means the PO-400's reply shape (PROTOCOL.md §3, `81 01`): `F1`, eight printable ASCII
    bytes, and a checksum equal to the sum of the nine bytes before it mod 128.
    """
    for i in range(len(data) - 9):
        frame = data[i:i + 10]
        if frame[0] != 0xF1 or frame[9] != sum(frame[:9]) & 0x7F:
            continue
        if all(0x20 <= b < 0x7F for b in frame[1:9]):
            return frame[1:9].decode("ascii").strip()
    return None


def probe_model(backend, timeout: float = PROBE_TIMEOUT_SEC) -> Optional[str]:
    """Asks a just-opened device for its model; None if it does not answer like an oximeter.

    Sends what `info` sends first (unlock, then `81 01`), so an oximeter sees nothing new. A
    foreign device on the same USB ID receives these 16 bytes once; there is no way to ask a
    serial device what it is without writing to it (SpO2 Assistant does the same).
    """
    backend.write_report(build_unlock_negotiate_handshake())
    backend.write_report(build_hid_command(0x81, [0x01]))
    data = b""
    start = time.time()
    while time.time() - start < timeout:
        rep = backend.read_report(64)
        if rep:
            data += rep
            model = find_model_frame(data)
            if model is not None:
                # Drop anything else the probe stirred up, but never wait on a device that
                # keeps streaming (live mode left on): a few reads at most.
                for _ in range(16):
                    if not backend.read_report(64):
                        break
                return model
        else:
            time.sleep(0.02)
    return None


class _PosixPort:
    """A raw, non-blocking serial port via termios."""

    def __init__(self, path: str):
        import termios
        self._termios = termios
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            attrs = termios.tcgetattr(self.fd)
            iflag, oflag, cflag, lflag, _ispeed, _ospeed, cc = attrs
            iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
                       | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON
                       | termios.IXOFF | termios.IXANY)
            oflag &= ~termios.OPOST
            lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
            cflag &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB)
            cflag |= termios.CS8 | termios.CREAD | termios.CLOCAL
            if hasattr(termios, "CRTSCTS"):
                cflag &= ~termios.CRTSCTS
            cc = list(cc)
            cc[termios.VMIN] = 0
            cc[termios.VTIME] = 0
            speed = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, speed, speed, cc])
            termios.tcflush(self.fd, termios.TCIOFLUSH)
            if hasattr(termios, "TIOCEXCL"):  # keep other programs (e.g. ModemManager) off the port
                import fcntl
                fcntl.ioctl(self.fd, termios.TIOCEXCL)
        except Exception:
            os.close(self.fd)
            raise

    def write(self, data: bytes) -> int:
        """Writes all of `data`. The fd is non-blocking, so a full output buffer means a short
        write or EAGAIN; retry for up to a second instead of silently dropping bytes."""
        view, deadline = memoryview(data), time.time() + 1.0
        while view:
            try:
                n = os.write(self.fd, view)
            except BlockingIOError:
                n = 0
            view = view[n:]
            if view:
                if time.time() > deadline:
                    raise OSError(f"serial write timed out with {len(view)} of {len(data)} bytes unsent")
                time.sleep(0.002)
        return len(data)

    def read(self, n: int) -> bytes:
        try:
            return os.read(self.fd, n)
        except BlockingIOError:
            return b""

    def close(self) -> None:
        os.close(self.fd)


class _WindowsPort:
    """A raw serial port via the Win32 COM API (ctypes). Reads return at once."""

    def __init__(self, path: str):
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32 = k32
        # Explicit argtypes: without them ctypes passes ints as 32-bit C ints, which truncates a
        # 64-bit HANDLE and overflows on GENERIC_READ (0x80000000).
        H, D, P = wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, D, D, P, D, D, H]
        k32.CreateFileW.restype = H
        k32.GetCommState.argtypes = [H, P]
        k32.SetCommState.argtypes = [H, P]
        k32.SetCommTimeouts.argtypes = [H, P]
        k32.PurgeComm.argtypes = [H, D]
        k32.WriteFile.argtypes = [H, ctypes.c_char_p, D, ctypes.POINTER(D), P]
        k32.ReadFile.argtypes = [H, ctypes.c_char_p, D, ctypes.POINTER(D), P]
        k32.CloseHandle.argtypes = [H]
        name = path if path.startswith("\\\\.\\") else "\\\\.\\" + path
        GENERIC_READ, GENERIC_WRITE, OPEN_EXISTING = 0x80000000, 0x40000000, 3
        handle = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        if handle in (None, wintypes.HANDLE(-1).value):
            raise OSError(ctypes.get_last_error(), f"cannot open {path}")
        self.handle = handle

        class DCB(ctypes.Structure):
            _fields_ = [("DCBlength", wintypes.DWORD), ("BaudRate", wintypes.DWORD),
                        ("fBits", wintypes.DWORD), ("wReserved", wintypes.WORD),
                        ("XonLim", wintypes.WORD), ("XoffLim", wintypes.WORD),
                        ("ByteSize", ctypes.c_ubyte), ("Parity", ctypes.c_ubyte),
                        ("StopBits", ctypes.c_ubyte), ("XonChar", ctypes.c_char),
                        ("XoffChar", ctypes.c_char), ("ErrorChar", ctypes.c_char),
                        ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
                        ("wReserved1", wintypes.WORD)]

        class COMMTIMEOUTS(ctypes.Structure):
            _fields_ = [("ReadIntervalTimeout", wintypes.DWORD),
                        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
                        ("ReadTotalTimeoutConstant", wintypes.DWORD),
                        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
                        ("WriteTotalTimeoutConstant", wintypes.DWORD)]

        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if not k32.GetCommState(handle, ctypes.byref(dcb)):
            self.close()
            raise OSError(ctypes.get_last_error(), f"GetCommState failed on {path}")
        dcb.BaudRate = BAUD_RATE
        dcb.ByteSize, dcb.Parity, dcb.StopBits = 8, 0, 0  # 8N1
        # fBinary, DTR and RTS on (as a POSIX open leaves them), no flow control, no parity check.
        dcb.fBits = 0x0001 | 0x0010 | 0x1000
        if not k32.SetCommState(handle, ctypes.byref(dcb)):
            self.close()
            raise OSError(ctypes.get_last_error(), f"SetCommState failed on {path}")
        # MAXDWORD, 0, 0: ReadFile returns immediately with whatever has arrived.
        timeouts = COMMTIMEOUTS(0xFFFFFFFF, 0, 0, 0, 1000)
        k32.SetCommTimeouts(handle, ctypes.byref(timeouts))
        k32.PurgeComm(handle, 0x0004 | 0x0008)  # PURGE_TXCLEAR | PURGE_RXCLEAR

    def write(self, data: bytes) -> int:
        from ctypes import wintypes
        written = wintypes.DWORD(0)
        if not self._k32.WriteFile(self.handle, bytes(data), len(data), self._ctypes.byref(written), None):
            raise OSError(self._ctypes.get_last_error(), "WriteFile failed")
        if written.value != len(data):
            raise OSError(f"serial write timed out with {len(data) - written.value} of {len(data)} bytes unsent")
        return written.value

    def read(self, n: int) -> bytes:
        from ctypes import wintypes
        buf = self._ctypes.create_string_buffer(n)
        got = wintypes.DWORD(0)
        if not self._k32.ReadFile(self.handle, buf, n, self._ctypes.byref(got), None):
            raise OSError(self._ctypes.get_last_error(), "ReadFile failed")
        return buf.raw[:got.value]

    def close(self) -> None:
        if self.handle is not None:
            self._k32.CloseHandle(self.handle)
            self.handle = None


def open_port(path: str):
    """Opens a serial port for the backend. Tests replace this with a simulated port."""
    if sys.platform == "win32":
        return _WindowsPort(path)
    return _PosixPort(path)


def no_serial_device_message() -> str:
    return (
        "No supported oximeter found (PO-400 over HID, or a USB-serial Contec model). "
        "Ensure the USB cable is plugged in and the device is powered ON."
    )


class SerialBackend:
    """USB-serial backend with the HID backends' interface (connect/write_report/read_report).

    Writes send a report's command bytes without its padding (`unpad_report`). Reads cut the
    incoming byte stream at quiet gaps, so a reply starts a "report" the way it does on HID
    and the engine's parsers work unchanged.
    """

    def __init__(self, dev_path: Optional[str] = None):
        self.dev_path = dev_path
        self._port = None
        self._pending = b""
        self._usb_id: Optional[Tuple[str, str]] = None
        self.model_string: Optional[str] = None  # from the probe

    def connect(self) -> str:
        """Opens the port. Every port is probed first (`probe_model`): without --device, only a
        candidate that answers like an oximeter is used; a chosen port that does not answer is
        used anyway, with a warning."""
        if self.dev_path:
            self._open(self.dev_path)
            self.model_string = probe_model(self)
            if self.model_string is None:
                print(f"⚠️ {self.dev_path} did not answer like an oximeter; continuing because you chose it.")
            return self.dev_path

        candidates = find_serial_candidates()
        if not candidates:
            raise RuntimeError(no_serial_device_message())
        chosen, answered, skipped = None, [], []
        for port, vid, pid in candidates:
            other = SerialBackend(port)
            try:
                other._open(port)
            except Exception as e:
                skipped.append(f"{port} ({vid}:{pid}): {e}")
                continue
            model = probe_model(other)
            if model is None:
                other.close()
                print(f"Probing {port} ({vid}:{pid})... not an oximeter, skipped")
                skipped.append(f"{port} ({vid}:{pid}) did not answer like an oximeter")
                continue
            answered.append(port)
            if chosen is None:
                chosen = (other, port, vid, pid, model)
            else:
                other.close()
        if chosen is None:
            raise RuntimeError("No oximeter answered on the serial port(s) found: " + "; ".join(skipped))
        other, port, vid, pid, model = chosen
        self._port, other._port = other._port, None
        self.dev_path, self._usb_id, self.model_string = port, (vid, pid), model
        if len(answered) > 1:
            print(f"Oximeters answered on {', '.join(answered)}; using {port}. Pick another with --device.")
        return port

    def _open(self, path: str) -> None:
        try:
            self._port = open_port(path)
            self._pending = b""
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied accessing '{path}'. On Linux, add your user to the "
                "'dialout' group (then log out and in again)."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to open serial port '{path}': {e}") from e

    def is_connected(self) -> bool:
        return self._port is not None

    def write_report(self, report_bytes: bytes) -> int:
        if self._port is None:
            raise RuntimeError("Device is not connected.")
        data = unpad_report(report_bytes)
        if data:
            self._port.write(data)
        return len(report_bytes)  # what the engine handed in, as a HID write reports

    def read_report(self, max_bytes: int = REPORT_SIZE) -> Optional[bytes]:
        if self._port is None:
            raise RuntimeError("Device is not connected.")
        if not self._pending:
            self._pending = self._port.read(256)
            if not self._pending:
                return None
            # Keep reading until the line goes quiet or a full report has arrived.
            while len(self._pending) < max_bytes:
                time.sleep(QUIET_GAP_SEC)
                more = self._port.read(256)
                if not more:
                    break
                self._pending += more
        out, self._pending = self._pending[:max_bytes], self._pending[max_bytes:]
        return out

    def read_report_blocking(self, max_bytes: int = REPORT_SIZE, timeout_sec: float = 2.0) -> Optional[bytes]:
        start = time.time()
        while time.time() - start < timeout_sec:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def get_descriptor_info(self) -> dict:
        vid, pid = self._usb_id or (None, None)
        if vid is None and self.dev_path:
            for port, v, p in find_serial_candidates():
                if port == self.dev_path:
                    vid, pid = v, p
                    break
        return {
            "manufacturer": None,
            "product": None,
            "serial_number": None,
            "release_number": None,
            "bus_path": None,
            "hid_id": None,
            "hid_name": None,
            "vid_hex": vid,
            "pid_hex": pid,
            "metadata_source": f"USB-serial port {self.dev_path} ({BAUD_RATE} baud)",
        }

    def close(self):
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
            self._port = None
