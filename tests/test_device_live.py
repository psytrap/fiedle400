"""Physical Hardware Integration Tests for Pulsox PO-400 USB HID Device.

This test suite executes end-to-end communication tests directly against
a connected physical PO-400 device.

When no physical device is detected (or in headless CI environments),
the entire suite is automatically skipped to prevent test failures.
"""

import sys
import unittest
from datetime import datetime

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


@unittest.skipUnless(is_device_connected(), "No physical Pulsox PO-400 device connected or accessible.")
class TestLiveDevice(unittest.TestCase):
    """End-to-end hardware tests against real Pulsox PO-400 device."""

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
        self.assertFalse(dev.is_connected())

    def test_04_handshake_and_device_info(self):
        """Verifies hardware handshake and reads device info descriptors from firmware."""
        dev = PulsoxHidDevice()
        dev.connect()
        try:
            engine = SerialDeviceEngine(dev)
            res = engine.read_device_info(debug=0)

            self.assertIn("device_info", res)
            self.assertIn("active_user_id", res)
            self.assertIn("rtc_time_str", res)

            info = res["device_info"]
            self.assertEqual(res["active_user_id"], 1)
            self.assertEqual(info.flash_geometry, "112 Bytes Sub-chunk Payload")
            self.assertEqual(info.user_profile, "user")
            self.assertNotEqual(res["rtc_time_str"], "N/A")
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
                self.assertGreaterEqual(sess.session_id, 1)
                self.assertGreaterEqual(sess.record_count, 0)
                self.assertGreaterEqual(sess.duration_sec, 0)
        finally:
            dev.close()


if __name__ == "__main__":
    unittest.main()
