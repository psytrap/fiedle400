"""Mock-hardware tests: the real HidBackend code path (Windows and macOS) against the
same simulated PO-400 used for Linux.

Unlike tests/test_hwsim_linux.py and tests/test_hwsim_realtrace.py, nothing here is
Linux-gated: HidBackend never touches a kernel node, only plain `hid` module calls, so
the fake (tests/hwsim.py's FakeHidDevice / make_fake_hid_module) needs no OS emulation
and this file runs on every CI platform, every push.

Primary coverage is the "cython" hid shape (`hid.device`), because that is what PyPI
`hidapi` provides and what build-release.yml installs for the shipped binary -- the
code path real Windows and macOS users actually run. The "ctypes" shape (`hid.Device`,
PyPI `hid`) gets a lighter smoke test: enough to prove HidBackend.connect() takes that
branch correctly, not a full duplicate of every flow.

This proves the *code's* behaviour on the backend Windows/macOS use. It cannot prove
how the real Windows HID stack behaves -- the W1-W5 hypotheses in
handoff/ci-mock-hardware-response.md need the physical laptop regardless.

The T1/T3/T4/T6/T7 defects first pinned as expected failures in tests/test_hwsim_realtrace.py
(RELEASE_PLAN.md section 3d) are protocol-level, not backend-specific, so they reproduced here
too, through a completely different transport. They are fixed; these tests now assert the correct
behaviour on this backend as well.
"""

import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hwsim  # noqa: E402
from hwsim import FakeOximeter, VirtualClock, command_key, make_fake_hid_module  # noqa: E402
import test_hwsim_realtrace as rt  # noqa: E402  (module import only: its test classes are not collected here)

from fiedle400 import cli  # noqa: E402
from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402


def run_cli(argv, fake_module):
    """Run the CLI's main() with stdout/stderr captured, hid faked, exit() caught."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(sys.modules, {"hid": fake_module}), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main(argv)
            rc = 0
        except SystemExit as e:
            rc = e.code or 0
    return rc, out.getvalue(), err.getvalue()


# --------------------------------------------------------------------------
# Whole flows through HidBackend, engine, detector, export and the CLI
# --------------------------------------------------------------------------
class FlowCase(unittest.TestCase):
    style = "cython"  # the shape CI and the shipped binary actually use

    def make_fake(self) -> FakeOximeter:
        return FakeOximeter(rt.real_trace(), strict=True)

    def setUp(self):
        self.fake = self.make_fake()
        self.fake_module = make_fake_hid_module(self.fake, style=self.style)
        patcher = mock.patch.dict(sys.modules, {"hid": self.fake_module})
        patcher.start()
        self.addCleanup(patcher.stop)
        # Same engine code as the Linux flows: time.sleep() in its polling
        # loops is real whichever backend sits underneath, so speed it up
        # the same way HidrawSim's tests do (fiedle400.engine.device.time).
        clock_patch = VirtualClock().patch()
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.dev = PulsoxHidDevice(backend="hid")
        self.dev.connect()
        self.addCleanup(self.dev.close)
        self.engine = SerialDeviceEngine(self.dev)

    def assert_fully_answered(self):
        self.assertEqual([r.hex()[:24] for r in self.fake.unmatched], [])
        self.assertEqual(self.fake.destructive, [])

    def download(self):
        sess = self.engine.list_sessions()[0]
        with contextlib.redirect_stdout(io.StringIO()):
            return self.engine.download_session(sess)

    def run_info(self):
        return run_cli(["info", "--backend", "hid"], self.fake_module)


class TestSessions(FlowCase):
    def test_lists_the_recorded_session(self):
        (s,) = self.engine.list_sessions()
        self.assertEqual((s.session_id, s.user_id, s.record_count, s.raw_samples), (1, 1, 107, 214))
        self.assertEqual(s.timestamp.isoformat(), "2026-09-30T19:54:53")
        self.assert_fully_answered()

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual([command_key(r) for r in self.fake.sent], [("unlock",), (0x9C, 0x80), (0x9C, 1)])

    def test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds(self):
        """T3 (fixed), same as on Linux: 214 raw samples at 2 Hz are 107 s."""
        (s,) = self.engine.list_sessions()
        self.assertEqual(s.duration_seconds, 107)


class TestDownload(FlowCase):
    def test_ends_with_the_non_destructive_segment_ack(self):
        self.download()
        self.assertEqual(command_key(self.fake.sent[-1]), (0x9D, 2))

    def test_no_retries_when_every_request_is_answered(self):
        self.download()
        self.assertEqual(len(self.fake.sent), 8)
        self.assert_fully_answered()

    def test_download_returns_107_records_not_214(self):
        """T6/T1 (fixed), same as on Linux: one window, each sample once, through HidBackend."""
        records = self.download()
        self.assertEqual(len(records), 107)
        self.assertEqual([r["spo2"] for r in records], rt.pairs(rt.window(rt.SPO2, 0)))
        self.assertEqual([r["flags"] for r in records], ["ok"] * 107)


class TestInfo(FlowCase):
    def test_clock_and_user_come_from_recorded_replies(self):
        res = self.engine.read_device_info()
        self.assertEqual(res["rtc_time_str"], "2002-07-01 12:07:00")
        self.assertEqual(res["device_info"].user_profile, "user")
        self.assert_fully_answered()

    def test_firmware_serial_and_geometry_are_not_made_up(self):
        """T4/T7 (fixed), same as on Linux."""
        rc, out, err = self.run_info()
        self.assertEqual(rc, 0)
        self.assertNotIn("v2.0 (CMS-60D/PO-400 v2)", out)
        self.assertNotIn("112 Bytes Sub-chunk Payload", out)
        for label in ("Firmware Version", "Serial Number", "Storage Memory Geometry"):
            self.assertRegex(out, rf"{label}\s*: not reported by the device")

    def test_the_model_descriptor_is_shown_as_such(self):
        rc, out, err = self.run_info()
        self.assertRegex(out, r"Device Model Descriptor\s*: 50F")


# --------------------------------------------------------------------------
# Fault paths HidBackend itself must handle, not FakeOximeter
# --------------------------------------------------------------------------
class TestConnectionFaults(unittest.TestCase):
    def test_no_device_found_raises_a_clear_error_not_a_crash(self):
        fake_module = make_fake_hid_module(FakeOximeter(rt.real_trace()), present=False)
        with mock.patch.dict(sys.modules, {"hid": fake_module}):
            with self.assertRaises(RuntimeError) as ctx:
                PulsoxHidDevice(backend="hid").connect()
            self.assertIn("No Pulsox PO-400 device found", str(ctx.exception))

    def test_a_broken_enumerate_is_reported_as_an_installation_problem_not_a_missing_device(self):
        """Regression guard for the bug fixed in 0ab3bf0: hid.enumerate() raising must not
        be swallowed into the same message as a genuinely absent device."""
        fake_module = make_fake_hid_module(FakeOximeter(rt.real_trace()))

        def broken_enumerate(vid, pid):
            raise OSError("hidapi failed to load its native library")

        fake_module.enumerate = broken_enumerate
        with mock.patch.dict(sys.modules, {"hid": fake_module}):
            with self.assertRaises(RuntimeError) as ctx:
                PulsoxHidDevice(backend="hid").connect()
            self.assertIn("installation problem", str(ctx.exception))


# --------------------------------------------------------------------------
# The other real `hid` package shape: proves the branch, not a full duplicate
# --------------------------------------------------------------------------
class TestCtypesStyleBranch(unittest.TestCase):
    """PyPI `hid` (apmorton/pyhidapi) exposes hid.Device, not hid.device. HidBackend
    branches on hasattr(hid, "Device") first (hid_driver.py), so this is the other half
    of that branch -- smoke-level, since the protocol logic is identical either way."""

    def test_connects_and_completes_the_handshake(self):
        fake = FakeOximeter(rt.real_trace(), strict=True)
        fake_module = make_fake_hid_module(fake, style="ctypes")
        with mock.patch.dict(sys.modules, {"hid": fake_module}):
            dev = PulsoxHidDevice(backend="hid")
            dev.connect()
            try:
                self.assertEqual(dev.backend_name, "hid")
                engine = SerialDeviceEngine(dev)
                (s,) = engine.list_sessions()
                self.assertEqual(s.record_count, 107)
            finally:
                dev.close()
        self.assertEqual(fake.destructive, [])


if __name__ == "__main__":
    unittest.main()
