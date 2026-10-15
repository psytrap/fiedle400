"""Mock tests for the live-device test harness: opt-in gate and cross-process lock."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_device_live as live


class TestLiveGate(unittest.TestCase):
    def test_suite_skipped_without_opt_in(self):
        if live.LIVE_ENABLED:
            self.skipTest("PO400_LIVE=1 is set; the gate is open on purpose")
        self.assertTrue(getattr(live.TestLiveDevice, "__unittest_skip__", False))

    def test_device_detection_not_run_at_import(self):
        """Importing the module must not probe the device (that made skip counts vary)."""
        import importlib
        with mock.patch("po400.hid_driver.find_pulsox_hid_devices", return_value=[]) as probe:
            importlib.reload(live)
        probe.assert_not_called()

    def test_opted_in_without_device_fails_loudly(self):
        with mock.patch.object(live, "is_device_connected", return_value=False), \
                mock.patch.object(live, "acquire_device_lock", return_value=None):
            with self.assertRaises(AssertionError) as cm:
                live.TestLiveDevice.setUpClass()
        self.assertIn("PO400_LIVE=1", str(cm.exception))


@unittest.skipIf(live.fcntl is None, "fcntl not available on this platform")
class TestDeviceLock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "live.lock")

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_process_waits_then_times_out(self):
        held = live.acquire_device_lock(self.path, timeout=1)
        try:
            script = textwrap.dedent(f"""
                import sys; sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r})
                import test_device_live as live
                try:
                    live.acquire_device_lock({self.path!r}, timeout=0.3)
                except TimeoutError:
                    sys.exit(3)
                sys.exit(0)
            """)
            rc = subprocess.run([sys.executable, "-c", script]).returncode
            self.assertEqual(rc, 3)
        finally:
            held.close()

    def test_lock_is_free_after_release(self):
        live.acquire_device_lock(self.path, timeout=1).close()
        again = live.acquire_device_lock(self.path, timeout=0.3)
        self.assertIsNotNone(again)
        again.close()


if __name__ == "__main__":
    unittest.main()
