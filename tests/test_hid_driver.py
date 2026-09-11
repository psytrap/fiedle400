"""Unit tests for PO-400 dual-backend HID driver (hidraw and hid)."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from po400.hid_driver import (
    HidBackend,
    LinuxHidrawBackend,
    PulsoxHidDevice,
    resolve_default_backend,
)


class TestHidDriverBackends(unittest.TestCase):
    """Test suite for driver backend resolution and abstraction."""

    def test_resolve_default_backend(self):
        with patch("sys.platform", "linux"):
            self.assertEqual(resolve_default_backend(), "hidraw")

        with patch("sys.platform", "win32"):
            self.assertEqual(resolve_default_backend(), "hid")

        with patch("sys.platform", "darwin"):
            self.assertEqual(resolve_default_backend(), "hid")

    def test_pulsox_hid_device_default_linux(self):
        with patch("sys.platform", "linux"):
            dev = PulsoxHidDevice(dev_path="/dev/hidraw1")
            self.assertEqual(dev.backend_name, "hidraw")
            self.assertIsInstance(dev._backend, LinuxHidrawBackend)

    def test_pulsox_hid_device_default_windows(self):
        with patch("sys.platform", "win32"):
            dev = PulsoxHidDevice()
            self.assertEqual(dev.backend_name, "hid")
            self.assertIsInstance(dev._backend, HidBackend)

    def test_pulsox_hid_device_explicit_hidraw_on_windows_fails(self):
        with patch("sys.platform", "win32"):
            with self.assertRaises(RuntimeError) as ctx:
                PulsoxHidDevice(backend="hidraw")
            self.assertIn("only supported on Linux", str(ctx.exception))

    def test_pulsox_hid_device_invalid_backend(self):
        with self.assertRaises(ValueError):
            PulsoxHidDevice(backend="invalid_backend")

    def test_hid_backend_missing_library(self):
        backend = HidBackend()
        with patch.dict(sys.modules, {"hid": None}):
            with self.assertRaises(RuntimeError) as ctx:
                backend.connect()
            self.assertIn("pip install hid", str(ctx.exception))

    def test_hid_backend_with_mock_cython_device(self):
        """Test with cython-hidapi style (hid.device)."""
        mock_hid = MagicMock(spec=["device", "enumerate"])
        mock_dev_inst = MagicMock()
        mock_hid.device.return_value = mock_dev_inst
        mock_hid.enumerate.return_value = [{"path": b"\\\\?\\hid#vid_28e9&pid_028a"}]

        with patch.dict(sys.modules, {"hid": mock_hid}):
            backend = HidBackend()
            connected_path = backend.connect()
            self.assertEqual(connected_path, "\\\\?\\hid#vid_28e9&pid_028a")
            mock_dev_inst.set_nonblocking.assert_called_once_with(1)

            # Test write_report prepends 0x00 Report ID for 64-byte payload
            payload_64 = bytes([0x7D] + [0x00] * 63)
            backend.write_report(payload_64)
            mock_dev_inst.write.assert_called_with(bytes([0x00]) + payload_64)

            # Test read_report
            mock_dev_inst.read.return_value = [0xF0, 0x70]
            data = backend.read_report(64)
            self.assertEqual(data, bytes([0xF0, 0x70]))

            # Test read_report empty
            mock_dev_inst.read.return_value = []
            self.assertIsNone(backend.read_report(64))

            # Test close
            backend.close()
            mock_dev_inst.close.assert_called_once()

    def test_hid_backend_with_mock_ctypes_device(self):
        """Test with ctypes hid style (hid.Device)."""
        mock_hid = MagicMock(spec=["Device", "enumerate"])
        mock_dev_inst = MagicMock()
        mock_hid.Device.return_value = mock_dev_inst
        mock_hid.enumerate.return_value = [{"path": b"/dev/hidraw10"}]

        with patch.dict(sys.modules, {"hid": mock_hid}):
            backend = HidBackend()
            connected_path = backend.connect()
            self.assertEqual(connected_path, "/dev/hidraw10")
            self.assertTrue(mock_dev_inst.nonblocking)

            payload_64 = bytes([0x7D] + [0x00] * 63)
            backend.write_report(payload_64)
            mock_dev_inst.write.assert_called_with(bytes([0x00]) + payload_64)

            backend.close()
            mock_dev_inst.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
