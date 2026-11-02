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
from hwsim import scrub_environment, FakeOximeter, Trace, VirtualClock, command_key, make_fake_hid_module  # noqa: E402
import test_hwsim_realtrace as rt  # noqa: E402  (module import only: its test classes are not collected here)

from fiedle400 import cli  # noqa: E402
from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402


def run_cli(argv, fake_module):
    """Run the CLI's main() with stdout/stderr captured, hid faked, exit() caught."""
    output, error_output = io.StringIO(), io.StringIO()
    with mock.patch.dict(sys.modules, {"hid": fake_module}), mock.patch.dict(os.environ), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
        scrub_environment()
        try:
            cli.main(argv)
            exit_code = 0
        except SystemExit as error:
            exit_code = error.code or 0
    return exit_code, output.getvalue(), error_output.getvalue()


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
        # T-088: the fake `hid` module isn't safe for a second thread to read from concurrently --
        # tell SerialDeviceEngine not to start its background reader thread even when a test
        # drives real CLI code that asks for one.
        from fiedle400.engine import device as device_module
        simulator_patcher = mock.patch.object(device_module, "SIMULATED_DEVICE_ACTIVE", True)
        simulator_patcher.start()
        self.addCleanup(simulator_patcher.stop)
        # Same engine code as the Linux flows: time.sleep() in its polling
        # loops is real whichever backend sits underneath, so speed it up
        # the same way HidrawSim's tests do (fiedle400.engine.device.time).
        clock_patch = VirtualClock().patch()
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.hid_device = PulsoxHidDevice(backend="hid")
        self.hid_device.connect()
        self.addCleanup(self.hid_device.close)
        self.engine = SerialDeviceEngine(self.hid_device)

    def assert_fully_answered(self):
        self.assertEqual([report.hex()[:24] for report in self.fake.unmatched], [])
        self.assertEqual(self.fake.destructive, [])

    def download(self):
        session = self.engine.list_sessions()[0]
        with contextlib.redirect_stdout(io.StringIO()):
            return self.engine.download_session(session)

    def run_info(self):
        return run_cli(["info", "--backend", "hid"], self.fake_module)


class TestSessions(FlowCase):
    def test_lists_the_recorded_session(self):
        (session,) = self.engine.list_sessions()
        self.assertEqual((session.session_id, session.user_id, session.record_count, session.raw_samples), (1, 1, 214, 214))
        self.assertEqual(session.timestamp.isoformat(), "2026-09-30T19:54:53")
        self.assert_fully_answered()

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual([command_key(report) for report in self.fake.sent], [("unlock",), (0x9C, 0x80), (0x9C, 1)])

    def test_header_count_is_seconds_so_duration_is_214_seconds(self):
        """T-075, same as on Linux: 214 samples, one per second, are 214 s."""
        (session,) = self.engine.list_sessions()
        self.assertEqual(session.duration_seconds, 214)


class TestDownload(FlowCase):
    def test_ends_with_the_non_destructive_segment_ack(self):
        self.download()
        self.assertEqual(command_key(self.fake.sent[-1]), (0x9D, 2))

    def test_no_retries_when_every_request_is_answered(self):
        self.download()
        self.assertEqual(len(self.fake.sent), 8)
        self.assert_fully_answered()

    def test_download_returns_each_sample_once(self):
        """T6/T1 (fixed), T-075, same as on Linux: one window, each sample once, through HidBackend."""
        records = self.download()
        self.assertEqual(len(records), 214)
        self.assertEqual([record["spo2"] for record in records], rt.window(rt.SPO2, 0))
        self.assertEqual([record["flags"] for record in records], ["ok"] * 214)


class TestInfo(FlowCase):
    def test_clock_and_user_come_from_recorded_replies(self):
        result = self.engine.read_device_info()
        self.assertEqual(result["rtc_time_text"], "not reported by the device")
        self.assertEqual(result["device_info"].user_profile, "user")
        self.assert_fully_answered()

    def test_firmware_serial_and_geometry_are_not_made_up(self):
        """T4/T7 (fixed), same as on Linux."""
        exit_code, output, error_output = self.run_info()
        self.assertEqual(exit_code, 0)
        self.assertNotIn("v2.0 (CMS-60D/PO-400 v2)", output)
        self.assertNotIn("112 Bytes Sub-chunk Payload", output)
        for label in ("Firmware Version", "Serial Number", "Storage Memory Geometry"):
            self.assertRegex(output, rf"{label}\s*: not reported by the device")

    def test_the_model_descriptor_is_shown_as_such(self):
        exit_code, output, error_output = self.run_info()
        self.assertRegex(output, r"Device Model Descriptor\s*: 50F")


class TestSelftest(FlowCase):
    """`fiedle400 selftest`: a read-only check with no FIEDLE400_LIVE needed.

    The second test guards a real defect found on real hardware (RELEASE_PLAN.md):
    a backend can ACK the unlock handshake but never answer anything past it (seen
    on this project's Linux hid/libusb install) without raising -- read_device_info
    and read_rtc_time both return falsy. selftest must treat that as a failure, not
    as "no exception means pass".
    """

    @unittest.skipUnless(sys.platform.startswith("linux"), "the sysfs check only runs on Linux")
    def test_unreadable_device_points_at_the_udev_setup_script(self):
        """A found-but-unreadable device is a permissions/udev problem, not a missing
        device -- selftest must say so and name the fix, not just "not readable"."""
        with mock.patch("fiedle400.hid_driver.find_pulsox_hid_devices",
                         return_value=[("/dev/hidraw0", "", False)]):
            exit_code, output, error_output = run_cli(["--backend", "hid", "selftest"], self.fake_module)
        self.assertEqual(exit_code, 1)
        self.assertIn("fiedle400_setup-udev.sh", output)

    def test_all_checks_pass_against_a_fully_answering_device(self):
        # Deliberately decoupled from trace-replay fidelity/ordering (unlike the
        # failure-mode test below, which IS an integration test of that replay):
        # this test is only about whether command_selftest correctly reports
        # success when the engine returns good data. Mocking the three engine
        # calls keeps it fast and immune to how many times a command was
        # recorded, command ordering across the suite, or anything else about
        # FakeOximeter's replay bookkeeping -- a real device answering every
        # query correctly is the scenario, not a specific trace file.
        info = mock.MagicMock()
        info.hardware_id = "50F"
        # command_selftest's sysfs-detection check (Linux only, unconditional
        # regardless of --backend) calls the REAL find_pulsox_hid_devices()
        # against the real filesystem. On a machine with the actual device
        # attached that passes by coincidence; on a CI runner with no USB
        # device at all it legitimately finds nothing -- this is what broke
        # CI (twice) despite passing locally every time. Faked here along
        # with the engine calls so the whole check is deterministic regardless
        # of what hardware the test happens to run on.
        with mock.patch("fiedle400.hid_driver.find_pulsox_hid_devices",
                         return_value=[("/dev/hidraw0", "", True)]), \
                mock.patch.object(SerialDeviceEngine, "read_device_info",
                                   return_value={"device_info": info}), \
                mock.patch.object(SerialDeviceEngine, "read_rtc_time",
                                   return_value=bytes.fromhex("f200000207000c07")), \
                mock.patch.object(SerialDeviceEngine, "list_sessions",
                                   return_value=[object()]):
            exit_code, output, error_output = run_cli(["--backend", "hid", "selftest"], self.fake_module)
        self.assertEqual(exit_code, 0, output + error_output)
        self.assertIn("All checks passed", output)
        self.assertNotIn("❌", output)  # no failure marker anywhere

    def test_backend_flag_also_works_after_the_subcommand(self):
        """`fiedle400 selftest -b hid` used to fail with "unrecognized arguments"; it takes -b like the others."""
        info = mock.MagicMock()
        info.hardware_id = "50F"
        with mock.patch("fiedle400.hid_driver.find_pulsox_hid_devices",
                         return_value=[("/dev/hidraw0", "", True)]), \
                mock.patch.object(SerialDeviceEngine, "read_device_info",
                                   return_value={"device_info": info}), \
                mock.patch.object(SerialDeviceEngine, "read_rtc_time",
                                   return_value=bytes.fromhex("f200000207000c07")), \
                mock.patch.object(SerialDeviceEngine, "list_sessions",
                                   return_value=[object()]):
            exit_code, output, error_output = run_cli(["selftest", "-b", "hid"], self.fake_module)
        self.assertEqual(exit_code, 0, output + error_output)
        self.assertIn("All checks passed", output)
        self.assertNotIn("❌", output)  # no failure marker anywhere

    def test_a_device_that_only_acks_and_never_answers_is_reported_as_failed(self):
        unresponsive = FakeOximeter(Trace())  # no recordings at all: ACKs unlock, answers nothing else
        fake_module = make_fake_hid_module(unresponsive)
        exit_code, output, error_output = run_cli(["--backend", "hid", "selftest"], fake_module)
        self.assertEqual(exit_code, 1, output + error_output)
        self.assertIn("Some checks failed", output)
        self.assertIn("no data returned", output)


# --------------------------------------------------------------------------
# Fault paths HidBackend itself must handle, not FakeOximeter
# --------------------------------------------------------------------------
class TestConnectionFaults(unittest.TestCase):
    def test_no_device_found_raises_a_clear_error_not_a_crash(self):
        fake_module = make_fake_hid_module(FakeOximeter(rt.real_trace()), present=False)
        with mock.patch.dict(sys.modules, {"hid": fake_module}):
            with self.assertRaises(RuntimeError) as context:
                PulsoxHidDevice(backend="hid").connect()
            self.assertIn("No Pulsox PO-400 device found", str(context.exception))

    def test_a_broken_enumerate_is_reported_as_an_installation_problem_not_a_missing_device(self):
        """Regression guard for the bug fixed in 0ab3bf0: hid.enumerate() raising must not
        be swallowed into the same message as a genuinely absent device."""
        fake_module = make_fake_hid_module(FakeOximeter(rt.real_trace()))

        def broken_enumerate(vid, pid):
            raise OSError("hidapi failed to load its native library")

        fake_module.enumerate = broken_enumerate
        with mock.patch.dict(sys.modules, {"hid": fake_module}):
            with self.assertRaises(RuntimeError) as context:
                PulsoxHidDevice(backend="hid").connect()
            self.assertIn("installation problem", str(context.exception))


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
            device = PulsoxHidDevice(backend="hid")
            device.connect()
            try:
                self.assertEqual(device.backend_name, "hid")
                engine = SerialDeviceEngine(device)
                (session,) = engine.list_sessions()
                self.assertEqual(session.record_count, 214)
            finally:
                device.close()
        self.assertEqual(fake.destructive, [])


if __name__ == "__main__":
    unittest.main()
