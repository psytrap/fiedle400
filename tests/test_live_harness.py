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
            self.skipTest("FIEDLE400_LIVE=1 is set; the gate is open on purpose")
        self.assertTrue(getattr(live.TestLiveDevice, "__unittest_skip__", False))

    def test_device_detection_not_run_at_import(self):
        """Importing the module must not probe the device (that made skip counts vary)."""
        import importlib
        with mock.patch("fiedle400.hid_driver.find_pulsox_hid_devices", return_value=[]) as probe:
            importlib.reload(live)
        probe.assert_not_called()

    def test_opted_in_without_device_fails_loudly(self):
        with mock.patch.object(live, "is_device_connected", return_value=False), \
                mock.patch.object(live, "acquire_device_lock", return_value=None):
            with self.assertRaises(AssertionError) as cm:
                live.TestLiveDevice.setUpClass()
        self.assertIn("FIEDLE400_LIVE=1", str(cm.exception))


class TestPlatformGating(unittest.TestCase):
    """Tests 01/02 are Linux-only off Linux; the hid-path tests stay enabled everywhere."""

    def _reload_as(self, platform):
        import importlib
        with mock.patch("sys.platform", platform):
            module = importlib.reload(live)
        self.addCleanup(importlib.reload, live)
        return module

    def test_linux_runs_all_hardware_tests(self):
        m = self._reload_as("linux")
        for name in ("test_01_device_detection", "test_02_hidraw_backend_connection_and_descriptors"):
            self.assertFalse(getattr(getattr(m.TestLiveDevice, name), "__unittest_skip__", False), name)

    def test_windows_skips_linux_only_tests_with_reason(self):
        m = self._reload_as("win32")
        for name in ("test_01_device_detection", "test_02_hidraw_backend_connection_and_descriptors"):
            fn = getattr(m.TestLiveDevice, name)
            self.assertTrue(getattr(fn, "__unittest_skip__", False), name)
            self.assertIn("win32", fn.__unittest_skip_why__)
        for name in ("test_01b_hid_enumeration", "test_03_hid_backend_connection_and_descriptors",
                     "test_04_handshake_and_device_info", "test_05_rtc_clock_read", "test_06_list_stored_sessions"):
            self.assertFalse(getattr(getattr(m.TestLiveDevice, name), "__unittest_skip__", False), name)

    def test_reattach_wait_is_noop_off_linux(self):
        with mock.patch("sys.platform", "win32"), \
                mock.patch.object(live, "find_pulsox_hid_devices") as probe:
            self.assertTrue(live.wait_for_hidraw_reattach(timeout=0.05))
        probe.assert_not_called()

    def test_reattach_wait_still_checks_on_linux(self):
        with mock.patch("sys.platform", "linux"), \
                mock.patch.object(live, "find_pulsox_hid_devices", return_value=[]):
            self.assertFalse(live.wait_for_hidraw_reattach(timeout=0.05, interval=0.01))

    def _fake_test(self):
        class T(unittest.TestCase):
            def runTest(self):
                pass
        return T()

    def test_missing_hid_fails_off_linux(self):
        with mock.patch.object(live, "IS_LINUX", False), mock.patch.dict(sys.modules, {"hid": None}):
            with self.assertRaises(AssertionError) as cm:
                live.import_hid_or_skip(self._fake_test())
        self.assertIn("pip install hidapi", str(cm.exception))

    def test_missing_hid_skips_on_linux(self):
        with mock.patch.object(live, "IS_LINUX", True), mock.patch.dict(sys.modules, {"hid": None}):
            with self.assertRaises(unittest.SkipTest):
                live.import_hid_or_skip(self._fake_test())


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
