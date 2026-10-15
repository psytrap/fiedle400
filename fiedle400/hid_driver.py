"""Pulsox PO-400 USB HID Device Driver.

Supports dual driver backends:
  - 'hidraw': Direct Linux kernel /dev/hidraw nodes (default on Linux, 0 external dependencies).
  - 'hid': Cross-platform HID library via `import hid` (default on Windows & macOS,
           selectable on Linux for cross-platform development/testing).
"""

import os
import sys
import time
from typing import List, Optional, Tuple

VENDOR_ID_HEX = "28E9"
PRODUCT_ID_HEX = "028A"
VENDOR_ID_INT = 0x28E9
PRODUCT_ID_INT = 0x028A


def resolve_default_backend() -> str:
    """Returns the default backend based on the host operating system.
    
    Linux defaults to 'hidraw' (zero dependencies).
    Windows and macOS default to 'hid'.
    """
    if sys.platform.startswith("linux"):
        return "hidraw"
    return "hid"


def find_pulsox_hid_devices() -> List[Tuple[str, str, bool]]:
    """Scans system for connected Pulsox PO-400 HID devices via Linux sysfs.
    
    Returns:
        List of tuples: (dev_path, uevent_info, is_readable)
    """
    found_devices = []
    sys_hidraw = "/sys/class/hidraw"

    if not os.path.exists(sys_hidraw):
        return found_devices

    for node in sorted(os.listdir(sys_hidraw)):
        uevent_path = os.path.join(sys_hidraw, node, "device", "uevent")
        if os.path.exists(uevent_path):
            try:
                with open(uevent_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if VENDOR_ID_HEX in content.upper() and PRODUCT_ID_HEX in content.upper():
                        dev_path = f"/dev/{node}"
                        is_readable = os.access(dev_path, os.R_OK | os.W_OK)
                        found_devices.append((dev_path, content.strip(), is_readable))
            except Exception:
                pass

    return found_devices


def get_usb_sysfs_info(dev_path: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Traverses sysfs tree dynamically to read USB Manufacturer, Product, and Bus ID.
    
    Returns:
        tuple: (manufacturer_str, product_str, bus_id)
    """
    node_name = os.path.basename(dev_path)
    sysfs_dev_dir = f"/sys/class/hidraw/{node_name}/device"
    
    if not os.path.exists(sysfs_dev_dir):
        return None, None, None

    real_path = os.path.realpath(sysfs_dev_dir)
    curr = real_path
    
    mfg, prod, bus_id = None, None, None
    
    # Traverse parent directory tree
    for _ in range(6):
        if not curr or curr == "/sys" or curr == "/":
            break
            
        mfg_file = os.path.join(curr, "manufacturer")
        prod_file = os.path.join(curr, "product")
        
        if os.path.exists(mfg_file) and mfg is None:
            try:
                with open(mfg_file, "r") as f:
                    mfg = f.read().strip()
            except Exception:
                pass
                
        if os.path.exists(prod_file) and prod is None:
            try:
                with open(prod_file, "r") as f:
                    prod = f.read().strip()
            except Exception:
                pass
                
        if mfg and prod:
            bus_id = os.path.basename(curr)
            break
        elif mfg or prod:
            if bus_id is None:
                bus_id = os.path.basename(curr)
            
        curr = os.path.dirname(curr)

    return mfg, prod, bus_id


class LinuxHidrawBackend:
    """Direct Linux /dev/hidraw driver backend using standard library POSIX file descriptors."""

    def __init__(self, dev_path: Optional[str] = None):
        self.dev_path = dev_path
        self._fd: Optional[int] = None

    def connect(self) -> str:
        """Locates and opens the HID device node."""
        if not self.dev_path:
            devices = find_pulsox_hid_devices()
            if not devices:
                raise RuntimeError(
                    "No Pulsox PO-400 device found! Ensure USB cable is plugged in and device is powered ON."
                )
            self.dev_path, _, is_readable = devices[0]
            if not is_readable:
                raise PermissionError(
                    f"Permission denied accessing '{self.dev_path}'. "
                    "Run 'sudo chmod 666 /dev/hidraw*' or set up udev rules."
                )

        try:
            o_flags = os.O_RDWR
            if hasattr(os, "O_NONBLOCK"):
                o_flags |= os.O_NONBLOCK
            self._fd = os.open(self.dev_path, o_flags)
            return self.dev_path
        except Exception as e:
            raise RuntimeError(f"Failed to open HID device '{self.dev_path}': {e}") from e

    def is_connected(self) -> bool:
        return self._fd is not None

    def write_report(self, report_bytes: bytes) -> int:
        if self._fd is None:
            raise RuntimeError("Device is not connected.")
        return os.write(self._fd, report_bytes)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self._fd is None:
            raise RuntimeError("Device is not connected.")
        try:
            data = os.read(self._fd, max_bytes)
            return data if data else None
        except BlockingIOError:
            return None

    def read_report_blocking(self, max_bytes: int = 64, timeout_sec: float = 2.0) -> Optional[bytes]:
        start = time.time()
        while time.time() - start < timeout_sec:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def get_descriptor_info(self) -> dict:
        """Extracts USB device descriptor and sysfs metadata on Linux."""
        sysfs_mfg, sysfs_prod, sysfs_bus = None, None, None
        hid_id = f"0003:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
        hid_name = "Pulse Oximeter"
        vid_hex, pid_hex = VENDOR_ID_HEX, PRODUCT_ID_HEX

        if self.dev_path and os.path.exists(self.dev_path):
            sysfs_mfg, sysfs_prod, sysfs_bus = get_usb_sysfs_info(self.dev_path)
            node_name = os.path.basename(self.dev_path)
            uevent_file = f"/sys/class/hidraw/{node_name}/device/uevent"
            if os.path.exists(uevent_file):
                try:
                    with open(uevent_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith("HID_ID="):
                                hid_id = line.strip().split("=", 1)[1]
                            elif line.startswith("HID_NAME="):
                                hid_name = line.strip().split("=", 1)[1]
                except Exception:
                    pass

        if ":" in hid_id:
            parts = hid_id.split(":")
            if len(parts) >= 3:
                vid_hex, pid_hex = parts[1], parts[2]

        clean_mfg = sysfs_mfg.strip() if (sysfs_mfg and sysfs_mfg.strip()) else None
        clean_prod = sysfs_prod.strip() if (sysfs_prod and sysfs_prod.strip()) else (hid_name.strip() if (hid_name and hid_name.strip()) else None)

        return {
            "manufacturer": clean_mfg,
            "product": clean_prod,
            "serial_number": None,
            "release_number": None,
            "bus_path": sysfs_bus,
            "hid_id": hid_id,
            "hid_name": hid_name,
            "vid_hex": vid_hex.upper()[-4:],
            "pid_hex": pid_hex.upper()[-4:],
            "metadata_source": "Linux sysfs (/sys/class/hidraw)",
        }

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None


def _no_device_message(enumerate_error: Optional[BaseException] = None) -> str:
    """Message for an empty enumeration, distinguishing a broken hidapi from an absent device."""
    if enumerate_error is not None:
        return (
            "The 'hid' library failed while scanning for devices: "
            f"{type(enumerate_error).__name__}: {enumerate_error}\n"
            "This is an installation problem, not a missing device -- hidapi "
            "could not load its native library."
        )
    return (
        "No Pulsox PO-400 device found via 'hid'! "
        "Ensure USB cable is plugged in and device is powered ON."
    )


class HidBackend:
    """Cross-platform driver backend using the `import hid` library."""

    def __init__(self, dev_path: Optional[str] = None):
        self.dev_path = dev_path
        self._dev = None
        self._enum_info = {}

    def _get_hid_module(self):
        try:
            import hid
            return hid
        except ImportError as e:
            raise RuntimeError(
                "The 'hid' library is required for the 'hid' backend but is not installed.\n"
                "Install it with: pip install hid\n"
                "(On Linux, the default 'hidraw' backend requires no extra libraries)."
            ) from e

    def connect(self) -> str:
        """Locates and opens the device via import hid."""
        hid = self._get_hid_module()

        try:
            connected_path = self.dev_path
            matched_list = []
            enumerate_error = None
            try:
                matched_list = hid.enumerate(VENDOR_ID_INT, PRODUCT_ID_INT)
                if matched_list:
                    self._enum_info = matched_list[0]
            except Exception as e:
                # A hidapi that cannot load its native library fails here. Keep
                # going (the explicit-path case below may still work) but hold
                # the error: reporting it as "no device found" sends people
                # hunting for a cable when the real fault is the install.
                enumerate_error = e

            if hasattr(hid, "Device"):
                # ctypes hid package (apmorton/pyhidapi)
                if self.dev_path:
                    path_bytes = self.dev_path.encode("utf-8") if isinstance(self.dev_path, str) else self.dev_path
                    dev_inst = hid.Device(path=path_bytes)
                else:
                    if not matched_list:
                        raise RuntimeError(_no_device_message(enumerate_error))
                    raw_path = matched_list[0].get("path")
                    if raw_path:
                        dev_inst = hid.Device(path=raw_path)
                        connected_path = raw_path.decode("utf-8", errors="ignore") if isinstance(raw_path, bytes) else str(raw_path)
                    else:
                        dev_inst = hid.Device(VENDOR_ID_INT, PRODUCT_ID_INT)
                        connected_path = f"hid:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
                dev_inst.nonblocking = True
            elif hasattr(hid, "device"):
                # cython-hidapi package (trezor/cython-hidapi)
                dev_inst = hid.device()
                if self.dev_path:
                    path_bytes = self.dev_path.encode("utf-8") if isinstance(self.dev_path, str) else self.dev_path
                    dev_inst.open_path(path_bytes)
                else:
                    if not matched_list:
                        raise RuntimeError(_no_device_message(enumerate_error))
                    raw_path = matched_list[0].get("path")
                    if raw_path:
                        dev_inst.open_path(raw_path)
                        connected_path = raw_path.decode("utf-8", errors="ignore") if isinstance(raw_path, bytes) else str(raw_path)
                    else:
                        dev_inst.open(VENDOR_ID_INT, PRODUCT_ID_INT)
                        connected_path = f"hid:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
                dev_inst.set_nonblocking(1)
            else:
                raise RuntimeError("Unsupported 'hid' module layout.")

            self._dev = dev_inst
            self.dev_path = connected_path or f"hid:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
            return self.dev_path
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Failed to open HID device via 'hid': {e}") from e

    def is_connected(self) -> bool:
        return self._dev is not None

    def write_report(self, report_bytes: bytes) -> int:
        if self._dev is None:
            raise RuntimeError("Device is not connected.")
        # On Windows / hid: prepends 0x00 Report ID for devices using unnumbered reports
        if len(report_bytes) == 64 and report_bytes[0] != 0x00:
            payload = bytes([0x00]) + report_bytes
        else:
            payload = report_bytes
        return self._dev.write(payload)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self._dev is None:
            raise RuntimeError("Device is not connected.")
        try:
            res = self._dev.read(max_bytes)
            return bytes(res) if res else None
        except Exception:
            return None

    def read_report_blocking(self, max_bytes: int = 64, timeout_sec: float = 2.0) -> Optional[bytes]:
        start = time.time()
        while time.time() - start < timeout_sec:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def get_descriptor_info(self) -> dict:
        """Extracts USB device descriptor metadata via import hid."""
        mfg = None
        prod = None
        serial = None
        release = None
        bus_path = None
        vid_hex = VENDOR_ID_HEX
        pid_hex = PRODUCT_ID_HEX

        # Check cached enumeration metadata if available
        if hasattr(self, "_enum_info") and self._enum_info:
            info = self._enum_info
            mfg = info.get("manufacturer_string")
            prod = info.get("product_string")
            serial = info.get("serial_number")
            release = info.get("release_number")
            if "interface_number" in info:
                bus_path = f"HID Interface #{info['interface_number']}"
            if "vendor_id" in info and "product_id" in info:
                vid_hex = f"{info['vendor_id']:04X}"
                pid_hex = f"{info['product_id']:04X}"

        # If device handle is open, query live strings if not already found
        if self._dev is not None:
            try:
                if not mfg:
                    if hasattr(self._dev, "get_manufacturer_string"):
                        mfg = self._dev.get_manufacturer_string()
                    elif hasattr(self._dev, "manufacturer"):
                        mfg = self._dev.manufacturer
                if not prod:
                    if hasattr(self._dev, "get_product_string"):
                        prod = self._dev.get_product_string()
                    elif hasattr(self._dev, "product"):
                        prod = self._dev.product
                if not serial:
                    if hasattr(self._dev, "get_serial_number_string"):
                        serial = self._dev.get_serial_number_string()
                    elif hasattr(self._dev, "serial"):
                        serial = self._dev.serial
            except Exception:
                pass

        clean_mfg = mfg.strip() if (mfg and isinstance(mfg, str) and mfg.strip()) else None
        clean_prod = prod.strip() if (prod and isinstance(prod, str) and prod.strip()) else None
        clean_serial = serial.strip() if (serial and isinstance(serial, str) and serial.strip()) else None

        release_str = None
        if release is not None and isinstance(release, int):
            release_str = f"v{release >> 8}.{release & 0xFF:02x} (BCD 0x{release:04X})"

        return {
            "manufacturer": clean_mfg,
            "product": clean_prod,
            "serial_number": clean_serial,
            "release_number": release_str,
            "bus_path": bus_path,
            "hid_id": f"0003:{vid_hex}:{pid_hex}",
            "hid_name": clean_prod,
            "vid_hex": vid_hex,
            "pid_hex": pid_hex,
            "metadata_source": "USB HID Descriptors (import hid)",
        }

    def close(self):
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None


# Backward compatibility alias
HidapiBackend = HidBackend


class PulsoxHidDevice:
    """Manager for communicating with the Pulsox PO-400 raw HID node.
    
    Supports 'hidraw' (default on Linux, 0 external dependencies) and
    'hid' (default on Windows/macOS, available on Linux for testing).
    """

    def __init__(self, dev_path: Optional[str] = None, backend: Optional[str] = None):
        self.dev_path = dev_path

        if backend is None:
            self.backend_name = resolve_default_backend()
        else:
            b = backend.lower().strip()
            if b in ("raw", "hidraw"):
                self.backend_name = "hidraw"
            elif b in ("hid", "api", "hidapi"):
                self.backend_name = "hid"
            else:
                raise ValueError(f"Unknown HID backend '{backend}'. Supported backends: 'hidraw', 'hid'.")

        if self.backend_name == "hidraw":
            if not sys.platform.startswith("linux"):
                raise RuntimeError(
                    f"The 'hidraw' backend is only supported on Linux (current OS: {sys.platform}).\n"
                    "On Windows and macOS, please use the 'hid' backend."
                )
            self._backend = LinuxHidrawBackend(dev_path=self.dev_path)
        else:
            self._backend = HidBackend(dev_path=self.dev_path)

    @property
    def _fd(self) -> Optional[int]:
        """Provides access to the underlying file descriptor when using LinuxHidrawBackend."""
        return getattr(self._backend, "_fd", None)

    @_fd.setter
    def _fd(self, val: Optional[int]):
        if hasattr(self._backend, "_fd"):
            self._backend._fd = val

    def connect(self) -> str:
        self.dev_path = self._backend.connect()
        return self.dev_path

    def is_connected(self) -> bool:
        return self._backend.is_connected()

    def write_report(self, report_bytes: bytes) -> int:
        return self._backend.write_report(report_bytes)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        return self._backend.read_report(max_bytes)

    def read_report_blocking(self, max_bytes: int = 64, timeout_sec: float = 2.0) -> Optional[bytes]:
        return self._backend.read_report_blocking(max_bytes, timeout_sec)

    def get_descriptor_info(self) -> dict:
        """Returns normalized USB hardware and descriptor metadata from the active backend."""
        if hasattr(self._backend, "get_descriptor_info"):
            return self._backend.get_descriptor_info()
        return {
            "manufacturer": None,
            "product": None,
            "serial_number": None,
            "release_number": None,
            "bus_path": None,
            "hid_id": f"0003:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}",
            "hid_name": None,
            "vid_hex": VENDOR_ID_HEX,
            "pid_hex": PRODUCT_ID_HEX,
            "metadata_source": "Default fallback",
        }

    def close(self):
        self._backend.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class MockHidDevice:
    """Mock HID Device simulator for offline parameter sweeps and unit testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.written = []
        self.backend_name = "mock"

    def connect(self) -> str:
        return "/dev/hidraw_mock"

    def is_connected(self) -> bool:
        return True

    def write_report(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self.responses:
            return self.responses.pop(0)
        # Default mock response: COMMAND_ACK (0xF0 0x70)
        return bytes([0xF0, 0x70] + [0x00] * 62)

    def read_report_blocking(self, max_bytes: int = 64, timeout_sec: float = 2.0) -> Optional[bytes]:
        return self.read_report(max_bytes)

    def get_descriptor_info(self) -> dict:
        return {
            "manufacturer": "Contec Medical Systems (Mock)",
            "product": "Pulse Oximeter (Mock)",
            "serial_number": "MOCK-50F",
            "release_number": "v1.00 (BCD 0x0100)",
            "bus_path": "Mock-USB-Bus",
            "hid_id": "0003:28E9:028A",
            "hid_name": "Pulse Oximeter Mock",
            "vid_hex": "28E9",
            "pid_hex": "028A",
            "metadata_source": "Mock Simulator",
        }

    def close(self):
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
