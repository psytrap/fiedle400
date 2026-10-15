"""Physical Hardware Integration Tests for Pulsox PO-400 USB HID Device.

This test suite executes end-to-end communication tests directly against
a connected physical PO-400 device.

The suite is opt-in: it only runs when PO400_LIVE=1 is set, so the default
`python3 -m unittest discover` run is pure mocks and its result does not depend
on whether (or in what state) a device happens to be attached. With
PO400_LIVE=1 and no reachable device, the suite fails loudly instead of
silently skipping.

    PO400_LIVE=1 python3 -m unittest tests.test_device_live -v
"""

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

from po400.hid_driver import (
    PulsoxHidDevice,
    find_pulsox_hid_devices,
)
from po400.serial_engine import SerialDeviceEngine


def is_device_connected() -> bool:
    """Checks if a physical Pulsox PO-400 device is connected and readable."""
    try:
        devs = find_pulsox_hid_devices()
        if devs and devs[0][2]:  # dev_path, uevent, is_readable
            return True
    except Exception:
        pass

    try:
        import hid
        matched = hid.enumerate(0x28E9, 0x028A)
        if matched:
            return True
    except Exception:
        pass

    return False


def wait_for_hidraw_reattach(timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Waits for the kernel hidraw node to come back after a libusb-backed open.

    The libusb build of the 'hid' module detaches the kernel usbhid driver while
    it holds the device, which makes /dev/hidraw* vanish for the duration. The
    node reappears a few tens of milliseconds after close, once udev has
    re-applied its rules. Without this barrier a fast-following hidraw test sees
    the missing node and fails with a misleading PermissionError.

    Returns True once a readable node is back, False if the timeout elapsed.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            devs = find_pulsox_hid_devices()
            if devs and devs[0][2]:  # dev_path, uevent, is_readable
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


LIVE_ENABLED = os.environ.get("PO400_LIVE") == "1"
LOCK_PATH = os.path.join(tempfile.gettempdir(), "po400-live-tests.lock")
LOCK_TIMEOUT_SEC = 120.0


def acquire_device_lock(path: str = LOCK_PATH, timeout: float = LOCK_TIMEOUT_SEC):
    """Serialises live-device test runs across processes.

    Two test processes opening the oximeter at once collide (and the libusb
    backend even makes /dev/hidraw* vanish for the other one), producing
    failures that are not real. Returns the open lock file, or None where
    fcntl is unavailable. Raises TimeoutError if another run holds the lock.
    """
    if fcntl is None:
        return None
    fh = open(path, "w")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except BlockingIOError:
            if time.monotonic() >= deadline:
                fh.close()
                raise TimeoutError(f"Another live-device test run still holds {path} after {timeout:.0f}s.")
            time.sleep(0.1)


@unittest.skipUnless(LIVE_ENABLED, "Hardware tests are opt-in: set PO400_LIVE=1 with a PO-400 attached.")
class TestLiveDevice(unittest.TestCase):
    """End-to-end hardware tests against real Pulsox PO-400 device."""

    @classmethod
    def setUpClass(cls):
        cls._lock = acquire_device_lock()
        # Detect at run time (not import time), right before the tests use the device.
        if not is_device_connected():
            cls._release_lock()
            raise AssertionError(
                "PO400_LIVE=1 but no readable Pulsox PO-400 was found "
                "(check the USB cable, power, and the udev rules in README.md)."
            )

    @classmethod
    def tearDownClass(cls):
        cls._release_lock()

    @classmethod
    def _release_lock(cls):
        lock = getattr(cls, "_lock", None)
        if lock is not None:
            lock.close()  # closing the file releases the flock
            cls._lock = None

    def test_01_device_detection(self):
        """Verifies that find_pulsox_hid_devices discovers the connected hardware."""
        devices = find_pulsox_hid_devices()
        self.assertTrue(len(devices) >= 1, "Expected at least one PO-400 device detected via sysfs.")
        dev_path, uevent_str, is_readable = devices[0]
        self.assertTrue(dev_path.startswith("/dev/hidraw"))
        self.assertTrue(is_readable, f"Device node {dev_path} is not readable/writable by current user.")
        self.assertIn("000028E9", uevent_str.upper())
        self.assertIn("0000028A", uevent_str.upper())

    def test_02_hidraw_backend_connection_and_descriptors(self):
        """Verifies connection and descriptor extraction using native Linux hidraw."""
        dev = PulsoxHidDevice(backend="hidraw")
        node_path = dev.connect()
        try:
            self.assertTrue(dev.is_connected())
            self.assertEqual(dev.backend_name, "hidraw")
            self.assertTrue(node_path.startswith("/dev/hidraw"))

            meta = dev.get_descriptor_info()
            self.assertEqual(meta["vid_hex"], "28E9")
            self.assertEqual(meta["pid_hex"], "028A")
            self.assertIn("Linux sysfs", meta["metadata_source"])
        finally:
            dev.close()
        self.assertFalse(dev.is_connected())

    def test_03_hid_backend_connection_and_descriptors(self):
        """Verifies connection and descriptor extraction using cross-platform import hid."""
        try:
            import hid
        except ImportError:
            self.skipTest("The 'hid' library is not installed in the current environment.")

        dev = PulsoxHidDevice(backend="hid")
        node_path = dev.connect()
        try:
            self.assertTrue(dev.is_connected())
            self.assertEqual(dev.backend_name, "hid")

            meta = dev.get_descriptor_info()
            self.assertEqual(meta["vid_hex"], "28E9")
            self.assertEqual(meta["pid_hex"], "028A")
            self.assertIn("import hid", meta["metadata_source"])
        finally:
            dev.close()
            # Do not leak the detached-kernel-driver state into later hidraw tests.
            self.assertTrue(
                wait_for_hidraw_reattach(),
                "Kernel hidraw node did not reappear after closing the libusb-backed handle.",
            )
        self.assertFalse(dev.is_connected())

    def test_04_handshake_and_device_info(self):
        """Verifies hardware handshake and reads device info descriptors from firmware."""
        dev = PulsoxHidDevice()
        dev.connect()
        try:
            engine = SerialDeviceEngine(dev)
            res = engine.read_device_info(debug=0)

            self.assertIn("device_info", res, f"read_device_info result: {res!r}")
            self.assertIn("active_user_id", res, f"read_device_info result: {res!r}")
            self.assertIn("rtc_time_str", res, f"read_device_info result: {res!r}")

            info = res["device_info"]
            self.assertEqual(res["active_user_id"], 1, f"read_device_info result: {res!r}")
            self.assertEqual(info.flash_geometry, "112 Bytes Sub-chunk Payload", f"device_info: {info!r}")
            self.assertEqual(info.user_profile, "user", f"device_info: {info!r}")
            self.assertNotEqual(res["rtc_time_str"], "N/A", f"read_device_info result: {res!r}")
        finally:
            dev.close()

    def test_05_rtc_clock_read(self):
        """Verifies reading hardware Real-Time Clock (RTC) from device."""
        dev = PulsoxHidDevice()
        dev.connect()
        try:
            engine = SerialDeviceEngine(dev)
            rtc_dt = engine.read_rtc_time(debug=0)
            self.assertIsNotNone(rtc_dt, "Failed to read RTC time from device.")
            self.assertIsInstance(rtc_dt, datetime)
            self.assertTrue(rtc_dt.year >= 2000, f"Implausible RTC year: {rtc_dt.year}")
        finally:
            dev.close()

    def test_06_list_stored_sessions(self):
        """Verifies scanning flash memory index table for stored recording sessions."""
        dev = PulsoxHidDevice()
        dev.connect()
        try:
            engine = SerialDeviceEngine(dev)
            sessions = engine.list_sessions(debug=0)
            self.assertIsInstance(sessions, list)
            for sess in sessions:
                self.assertGreaterEqual(sess.session_id, 1, f"session: {sess!r}")
                self.assertGreaterEqual(sess.record_count, 0, f"session: {sess!r}")
                self.assertGreaterEqual(sess.duration_sec, 0, f"session: {sess!r}")
        finally:
            dev.close()


if __name__ == "__main__":
    unittest.main()
