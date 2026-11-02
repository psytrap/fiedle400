"""Pulsox PO-400 USB HID Device Driver.

Supports three driver backends:
  - 'hidraw': Direct Linux kernel /dev/hidraw nodes (default on Linux, 0 external dependencies).
  - 'hid': Cross-platform HID library via `import hid` (default on Windows & macOS,
           selectable on Linux for cross-platform development/testing).
  - 'serial': USB-serial Contec models (`serial_port.py`, T-101). Picked automatically
              when no HID device is found but a serial one is, or when --device names a
              serial port.
"""

import os
import sys
import time
from typing import List, Optional, Tuple

from .protocol.hardware import HID_USB_IDS
from . import serial_port

VENDOR_ID_HEX = "28E9"
PRODUCT_ID_HEX = "028A"
VENDOR_ID_INT = 0x28E9
PRODUCT_ID_INT = 0x028A

# Where the Linux kernel exposes hidraw nodes. Module constants (not literals in
# the functions) so the test suite can point them at a simulated tree.
SYSFS_HIDRAW_ROOT = "/sys/class/hidraw"
DEVICE_ROOT = "/dev"


def resolve_default_backend() -> str:
    """Returns the default backend based on the host operating system.

    Linux defaults to 'hidraw' (zero dependencies).
    Windows and macOS default to 'hid'.
    """
    if sys.platform.startswith("linux"):
        return "hidraw"
    return "hid"


def available_backends() -> List[str]:
    """Every backend this platform can attempt, default first.

    Linux can attempt both ('hidraw' then 'hid'); everywhere else only 'hid'
    exists ('hidraw' raises by design off Linux). Used so a one-command check
    (`fiedle400 selftest`) can cover every backend without the caller having
    to manually re-run it once per backend with `-b`.
    """
    if sys.platform.startswith("linux"):
        return ["hidraw", "hid"]
    return ["hid"]


def _uevent_matches(uevent: str) -> bool:
    """True if a hidraw uevent belongs to one of the HID IDs SpO2 Assistant scans (T-104)."""
    for line in uevent.splitlines():
        if line.startswith("HID_ID="):
            parts = line.split("=", 1)[1].strip().split(":")
            if len(parts) >= 3:
                try:
                    return (int(parts[1], 16), int(parts[2], 16)) in HID_USB_IDS
                except ValueError:
                    return False
    uevent_upper = uevent.upper()
    return any(f"{vid:04X}" in uevent_upper and f"{pid:04X}" in uevent_upper for vid, pid in HID_USB_IDS)


def find_pulsox_hid_devices() -> List[Tuple[str, str, bool]]:
    """Scans system for connected Contec HID oximeters (PO-400 and the other SpO2 Assistant HID ID) via Linux sysfs.
    
    Returns:
        List of tuples: (device_path, uevent_info, is_readable)
    """
    found_devices = []
    sys_hidraw = SYSFS_HIDRAW_ROOT

    if not os.path.exists(sys_hidraw):
        return found_devices

    for node in sorted(os.listdir(sys_hidraw)):
        uevent_path = os.path.join(sys_hidraw, node, "device", "uevent")
        if os.path.exists(uevent_path):
            try:
                with open(uevent_path, "r", encoding="utf-8", errors="ignore") as uevent:
                    content = uevent.read()
                    if _uevent_matches(content):
                        device_path = os.path.join(DEVICE_ROOT, node)
                        is_readable = os.access(device_path, os.R_OK | os.W_OK)
                        found_devices.append((device_path, content.strip(), is_readable))
            except Exception:
                pass

    return found_devices


def get_usb_sysfs_info(device_path: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Traverses sysfs tree dynamically to read USB Manufacturer, Product, and Bus ID.
    
    Returns:
        tuple: (manufacturer_str, product_str, bus_id)
    """
    node_name = os.path.basename(device_path)
    sysfs_device_directory = os.path.join(SYSFS_HIDRAW_ROOT, node_name, "device")
    
    if not os.path.exists(sysfs_device_directory):
        return None, None, None

    real_path = os.path.realpath(sysfs_device_directory)
    current = real_path
    
    manufacturer, prod, bus_id = None, None, None
    
    # Traverse parent directory tree
    for _ in range(6):
        if not current or current == "/sys" or current == "/":
            break
            
        manufacturer_file = os.path.join(current, "manufacturer")
        prod_file = os.path.join(current, "product")
        
        if os.path.exists(manufacturer_file) and manufacturer is None:
            try:
                with open(manufacturer_file, "r") as manufacturer_handle:
                    manufacturer = manufacturer_handle.read().strip()
            except Exception:
                pass
                
        if os.path.exists(prod_file) and prod is None:
            try:
                with open(prod_file, "r") as manufacturer_handle:
                    prod = manufacturer_handle.read().strip()
            except Exception:
                pass
                
        if manufacturer and prod:
            bus_id = os.path.basename(current)
            break
        elif manufacturer or prod:
            if bus_id is None:
                bus_id = os.path.basename(current)
            
        current = os.path.dirname(current)

    return manufacturer, prod, bus_id


class LinuxHidrawBackend:
    """Direct Linux /dev/hidraw driver backend using standard library POSIX file descriptors."""

    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self._file_descriptor: Optional[int] = None

    def connect(self) -> str:
        """Locates and opens the HID device node."""
        if not self.device_path:
            devices = find_pulsox_hid_devices()
            if not devices:
                raise RuntimeError(
                    "No Pulsox PO-400 device found! Ensure USB cable is plugged in and device is powered ON."
                )
            # The PO-400's own ID first: 0483:5751 is ST's generic HID ID and gets probed (T-104).
            devices.sort(key=lambda device_entry: 0 if "28E9" in device_entry[1].upper() else 1)
            self.device_path, _, is_readable = devices[0]
            if not is_readable:
                raise PermissionError(
                    f"Permission denied accessing '{self.device_path}'. "
                    "Run 'sudo chmod 666 /dev/hidraw*' or set up udev rules."
                )

        try:
            open_flags = os.O_RDWR
            if hasattr(os, "O_NONBLOCK"):
                open_flags |= os.O_NONBLOCK
            self._file_descriptor = os.open(self.device_path, open_flags)
            return self.device_path
        except Exception as error:
            raise RuntimeError(f"Failed to open HID device '{self.device_path}': {error}") from error

    def is_connected(self) -> bool:
        return self._file_descriptor is not None

    def write_report(self, report_bytes: bytes) -> int:
        if self._file_descriptor is None:
            raise RuntimeError("Device is not connected.")
        return os.write(self._file_descriptor, report_bytes)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self._file_descriptor is None:
            raise RuntimeError("Device is not connected.")
        try:
            data = os.read(self._file_descriptor, max_bytes)
            return data if data else None
        except BlockingIOError:
            return None

    def read_report_blocking(self, max_bytes: int = 64, timeout_seconds: float = 2.0) -> Optional[bytes]:
        start = time.time()
        while time.time() - start < timeout_seconds:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def get_descriptor_info(self) -> dict:
        """Extracts USB device descriptor and sysfs metadata on Linux."""
        sysfs_manufacturer, sysfs_prod, sysfs_bus = None, None, None
        hid_id = f"0003:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
        hid_name = "Pulse Oximeter"
        vid_hex, pid_hex = VENDOR_ID_HEX, PRODUCT_ID_HEX

        if self.device_path and os.path.exists(self.device_path):
            sysfs_manufacturer, sysfs_prod, sysfs_bus = get_usb_sysfs_info(self.device_path)
            node_name = os.path.basename(self.device_path)
            uevent_file = os.path.join(SYSFS_HIDRAW_ROOT, node_name, "device", "uevent")
            if os.path.exists(uevent_file):
                try:
                    with open(uevent_file, "r", encoding="utf-8", errors="ignore") as uevent:
                        for line in uevent:
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

        clean_manufacturer = sysfs_manufacturer.strip() if (sysfs_manufacturer and sysfs_manufacturer.strip()) else None
        clean_prod = sysfs_prod.strip() if (sysfs_prod and sysfs_prod.strip()) else (hid_name.strip() if (hid_name and hid_name.strip()) else None)

        return {
            "manufacturer": clean_manufacturer,
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
        if self._file_descriptor is not None:
            try:
                os.close(self._file_descriptor)
            except Exception:
                pass
            self._file_descriptor = None


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

    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self._device = None
        self._enum_info = {}

    def _get_hid_module(self):
        try:
            import hid
            return hid
        except ImportError as error:
            raise RuntimeError(
                "The 'hid' library is required for the 'hid' backend but is not installed "
                "(or no hidapi DLL/shared library could be found -- the 'hid' import module "
                "itself raises ImportError in that case too, T-063).\n"
                "Install it with: pip install hidapi\n"
                "(On Linux, the default 'hidraw' backend requires no extra libraries)."
            ) from error

    def _matched_ids(self) -> Tuple[int, int]:
        """VID/PID of the enumerated device, for opening it when hidapi gave no path."""
        info = self._enum_info or {}
        return info.get("vendor_id", VENDOR_ID_INT), info.get("product_id", PRODUCT_ID_INT)

    def connect(self) -> str:
        """Locates and opens the device via import hid."""
        hid = self._get_hid_module()

        try:
            connected_path = self.device_path
            matched_list = []
            enumerate_error = None
            try:
                for vid, pid in HID_USB_IDS:
                    matched_list = hid.enumerate(vid, pid)
                    if matched_list:
                        self._enum_info = matched_list[0]
                        break
            except Exception as e:
                # A hidapi that cannot load its native library fails here. Keep
                # going (the explicit-path case below may still work) but hold
                # the error: reporting it as "no device found" sends people
                # hunting for a cable when the real fault is the install.
                enumerate_error = e

            if hasattr(hid, "Device"):
                # ctypes hid package (apmorton/pyhidapi)
                if self.device_path:
                    path_bytes = self.device_path.encode("utf-8") if isinstance(self.device_path, str) else self.device_path
                    device = hid.Device(path=path_bytes)
                else:
                    if not matched_list:
                        raise RuntimeError(_no_device_message(enumerate_error))
                    raw_path = matched_list[0].get("path")
                    if raw_path:
                        device = hid.Device(path=raw_path)
                        connected_path = raw_path.decode("utf-8", errors="ignore") if isinstance(raw_path, bytes) else str(raw_path)
                    else:
                        vid, pid = self._matched_ids()
                        device = hid.Device(vid, pid)
                        connected_path = f"hid:{vid:04X}:{pid:04X}"
                device.nonblocking = True
            elif hasattr(hid, "device"):
                # cython-hidapi package (trezor/cython-hidapi)
                device = hid.device()
                if self.device_path:
                    path_bytes = self.device_path.encode("utf-8") if isinstance(self.device_path, str) else self.device_path
                    device.open_path(path_bytes)
                else:
                    if not matched_list:
                        raise RuntimeError(_no_device_message(enumerate_error))
                    raw_path = matched_list[0].get("path")
                    if raw_path:
                        device.open_path(raw_path)
                        connected_path = raw_path.decode("utf-8", errors="ignore") if isinstance(raw_path, bytes) else str(raw_path)
                    else:
                        vid, pid = self._matched_ids()
                        device.open(vid, pid)
                        connected_path = f"hid:{vid:04X}:{pid:04X}"
                device.set_nonblocking(1)
            else:
                raise RuntimeError("Unsupported 'hid' module layout.")

            self._device = device
            self.device_path = connected_path or f"hid:{VENDOR_ID_HEX}:{PRODUCT_ID_HEX}"
            return self.device_path
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Failed to open HID device via 'hid': {e}") from e

    def is_connected(self) -> bool:
        return self._device is not None

    def write_report(self, report_bytes: bytes) -> int:
        if self._device is None:
            raise RuntimeError("Device is not connected.")
        # On Windows / hid: prepends 0x00 Report ID for devices using unnumbered reports
        if len(report_bytes) == 64 and report_bytes[0] != 0x00:
            payload = bytes([0x00]) + report_bytes
        else:
            payload = report_bytes
        return self._device.write(payload)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self._device is None:
            raise RuntimeError("Device is not connected.")
        try:
            result = self._device.read(max_bytes)
            return bytes(result) if result else None
        except Exception:
            return None

    def read_report_blocking(self, max_bytes: int = 64, timeout_seconds: float = 2.0) -> Optional[bytes]:
        start = time.time()
        while time.time() - start < timeout_seconds:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def get_descriptor_info(self) -> dict:
        """Extracts USB device descriptor metadata via import hid."""
        manufacturer = None
        prod = None
        serial = None
        release = None
        bus_path = None
        vid_hex = VENDOR_ID_HEX
        pid_hex = PRODUCT_ID_HEX

        # Check cached enumeration metadata if available
        if hasattr(self, "_enum_info") and self._enum_info:
            info = self._enum_info
            manufacturer = info.get("manufacturer_string")
            prod = info.get("product_string")
            serial = info.get("serial_number")
            release = info.get("release_number")
            if "interface_number" in info:
                bus_path = f"HID Interface #{info['interface_number']}"
            if "vendor_id" in info and "product_id" in info:
                vid_hex = f"{info['vendor_id']:04X}"
                pid_hex = f"{info['product_id']:04X}"

        # If device handle is open, query live strings if not already found
        if self._device is not None:
            try:
                if not manufacturer:
                    if hasattr(self._device, "get_manufacturer_string"):
                        manufacturer = self._device.get_manufacturer_string()
                    elif hasattr(self._device, "manufacturer"):
                        manufacturer = self._device.manufacturer
                if not prod:
                    if hasattr(self._device, "get_product_string"):
                        prod = self._device.get_product_string()
                    elif hasattr(self._device, "product"):
                        prod = self._device.product
                if not serial:
                    if hasattr(self._device, "get_serial_number_string"):
                        serial = self._device.get_serial_number_string()
                    elif hasattr(self._device, "serial"):
                        serial = self._device.serial
            except Exception:
                pass

        clean_manufacturer = manufacturer.strip() if (manufacturer and isinstance(manufacturer, str) and manufacturer.strip()) else None
        clean_prod = prod.strip() if (prod and isinstance(prod, str) and prod.strip()) else None
        clean_serial = serial.strip() if (serial and isinstance(serial, str) and serial.strip()) else None

        release_text = None
        if release is not None and isinstance(release, int):
            release_text = f"v{release >> 8}.{release & 0xFF:02x} (BCD 0x{release:04X})"

        return {
            "manufacturer": clean_manufacturer,
            "product": clean_prod,
            "serial_number": clean_serial,
            "release_number": release_text,
            "bus_path": bus_path,
            "hid_id": f"0003:{vid_hex}:{pid_hex}",
            "hid_name": clean_prod,
            "vid_hex": vid_hex,
            "pid_hex": pid_hex,
            "metadata_source": "USB HID Descriptors (import hid)",
        }

    def close(self):
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None



class PulsoxHidDevice:
    """Manager for communicating with the Pulsox PO-400 raw HID node.
    
    Supports 'hidraw' (default on Linux, 0 external dependencies) and
    'hid' (default on Windows/macOS, available on Linux for testing).
    """

    def __init__(self, device_path: Optional[str] = None, backend: Optional[str] = None):
        self.device_path = device_path
        # With no backend chosen, a missing HID device falls back to a USB-serial one (T-101).
        self._auto_backend = backend is None and not device_path

        if backend is None:
            self.backend_name = "serial" if serial_port.is_serial_path(device_path) else resolve_default_backend()
        else:
            requested = backend.lower().strip()
            if requested in ("raw", "hidraw"):
                self.backend_name = "hidraw"
            elif requested in ("hid", "api", "hidapi"):
                self.backend_name = "hid"
            elif requested in ("serial", "com", "tty"):
                self.backend_name = "serial"
            else:
                raise ValueError(f"Unknown backend '{backend}'. Supported backends: 'hidraw', 'hid', 'serial'.")

        if self.backend_name == "serial":
            self._backend = serial_port.SerialBackend(device_path=self.device_path)
        elif self.backend_name == "hidraw":
            if not sys.platform.startswith("linux"):
                raise RuntimeError(
                    f"The 'hidraw' backend is only supported on Linux (current OS: {sys.platform}).\n"
                    "On Windows and macOS, please use the 'hid' backend."
                )
            self._backend = LinuxHidrawBackend(device_path=self.device_path)
        else:
            self._backend = HidBackend(device_path=self.device_path)

    @property
    def _file_descriptor(self) -> Optional[int]:
        """Provides access to the underlying file descriptor when using LinuxHidrawBackend."""
        return getattr(self._backend, "_file_descriptor", None)

    @_file_descriptor.setter
    def _file_descriptor(self, value: Optional[int]):
        if hasattr(self._backend, "_file_descriptor"):
            self._backend._file_descriptor = value

    def connect(self) -> str:
        try:
            self.device_path = self._backend.connect()
            self._probe_generic_hid()
        except RuntimeError as e:
            if not (self._auto_backend and str(e).startswith("No ")):  # no HID device, not a broken one
                raise
            if not serial_port.find_serial_candidates():
                raise
            self.backend_name = "serial"
            self._backend = serial_port.SerialBackend()
            self.device_path = self._backend.connect()
        return self.device_path

    def _probe_generic_hid(self) -> None:
        """0483:5751 is ST's generic HID demo ID, not an oximeter's own: probe it before use."""
        if self.backend_name == "serial":
            return
        try:
            meta = self._backend.get_descriptor_info()
        except Exception:
            return
        vid, pid = meta.get("vid_hex"), meta.get("pid_hex")
        if not isinstance(vid, str) or not isinstance(pid, str) or (vid.upper(), pid.upper()) != ("0483", "5751"):
            return
        if serial_port.probe_model(self._backend) is None:
            path = self.device_path
            self._backend.close()
            raise RuntimeError(f"No Pulsox PO-400 device found (the HID device 0483:5751 at {path} "
                               "did not answer like an oximeter).")

    @property
    def transport(self) -> str:
        """'serial' or 'hid', for messages (T-104)."""
        return "serial" if self.backend_name == "serial" else "hid"

    def is_connected(self) -> bool:
        return self._backend.is_connected()

    def write_report(self, report_bytes: bytes) -> int:
        return self._backend.write_report(report_bytes)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        return self._backend.read_report(max_bytes)

    def read_report_blocking(self, max_bytes: int = 64, timeout_seconds: float = 2.0) -> Optional[bytes]:
        return self._backend.read_report_blocking(max_bytes, timeout_seconds)

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

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
