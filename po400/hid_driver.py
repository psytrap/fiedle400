"""Pulsox PO-400 USB HID Device Driver.

Discovers and interfaces directly with raw Linux /dev/hidraw nodes for 
GigaDevice / Contec pulse oximeters (VID 0x28E9, PID 0x028A).
"""

import os
import stat
import time
from typing import List, Optional, Tuple

VENDOR_ID_HEX = "28E9"
PRODUCT_ID_HEX = "028A"


def find_pulsox_hid_devices() -> List[Tuple[str, str, bool]]:
    """Scans system for connected Pulsox PO-400 HID devices.
    
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


class PulsoxHidDevice:
    """Manager for communicating with the Pulsox PO-400 raw HID node."""

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
            self._fd = os.open(self.dev_path, os.O_RDWR | os.O_NONBLOCK)
            return self.dev_path
        except Exception as e:
            raise RuntimeError(f"Failed to open HID device '{self.dev_path}': {e}") from e

    def is_connected(self) -> bool:
        return self._fd is not None

    def write_report(self, report_bytes: bytes) -> int:
        """Sends a report to the HID device."""
        if self._fd is None:
            raise RuntimeError("Device is not connected.")
        return os.write(self._fd, report_bytes)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        """Reads a raw report from the HID device (non-blocking)."""
        if self._fd is None:
            raise RuntimeError("Device is not connected.")
        try:
            data = os.read(self._fd, max_bytes)
            return data if data else None
        except BlockingIOError:
            return None

    def read_report_blocking(self, max_bytes: int = 64, timeout_sec: float = 2.0) -> Optional[bytes]:
        """Polls for a report until received or timeout occurs."""
        start = time.time()
        while time.time() - start < timeout_sec:
            data = self.read_report(max_bytes)
            if data:
                return data
            time.sleep(0.02)
        return None

    def close(self):
        """Closes the file descriptor."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None

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

    def connect(self) -> str:
        return "/dev/hidraw_mock"

    def write_report(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        if self.responses:
            return self.responses.pop(0)
        # Default mock response: COMMAND_ACK (0xF0 0x70)
        return bytes([0xF0, 0x70] + [0x00] * 62)

    def close(self):
        pass

