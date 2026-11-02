"""The Arduino serial emulator (hardware/serial-emulator/) against fiedle400's real serial code.

The emulator's core (emulator.h) is built for the PC (host_sim.cpp) and served on a
pseudo-terminal, so these tests run SerialBackend over real termios, as on a USB-serial port.
They prove the sketch answers like the mock tests' FakeOximeter; how a real PO-250/PO-300
answers is still open (T-102). Skipped without a C++ compiler or pty.
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EMULATOR_DIRECTORY = os.path.join(ROOT, "hardware", "serial-emulator")
sys.path.insert(0, EMULATOR_DIRECTORY)
import make_trace  # noqa: E402

from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402

CXX = shutil.which("g++") or shutil.which("c++")


class TestTraceData(unittest.TestCase):
    def test_trace_data_h_matches_the_fixtures(self):
        with open(make_trace.OUT, encoding="utf-8") as file:
            self.assertEqual(file.read(), make_trace.render(),
                             "run python3 hardware/serial-emulator/make_trace.py")


@unittest.skipUnless(CXX and sys.platform != "win32", "needs a C++ compiler and a pseudo-terminal")
class TestHostSim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.binary = os.path.join(cls.tmp, "host_sim")
        subprocess.run([CXX, "-O2", "-o", cls.binary, os.path.join(EMULATOR_DIRECTORY, "host_sim.cpp")], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def connect(self, model="po400", faults="none"):
        link = os.path.join(self.tmp, "ttyACM-emu")
        simulator = subprocess.Popen([self.binary, link, model, faults], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(simulator.stdout.close)
        self.addCleanup(simulator.wait)
        self.addCleanup(simulator.kill)
        simulator.stdout.readline()  # the link exists once this is printed
        device = PulsoxHidDevice(device_path=link)
        with contextlib.redirect_stdout(io.StringIO()):
            device.connect()
        self.addCleanup(device.close)
        return device, SerialDeviceEngine(device)

    def quietly(self, function, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args)

    def test_po400_probe_lists_and_downloads_the_214_second_auto_recording(self):
        device, engine = self.connect()
        self.assertEqual(device._backend.model_string, "50F")
        (session,) = self.quietly(engine.list_sessions)
        self.assertEqual((session.manual, session.record_count), (False, 214))
        self.assertEqual(len(self.quietly(engine.download_session, session)), 214)

    def test_po250_has_only_the_manual_recording_and_a_placeholder_model(self):
        device, engine = self.connect("po250")
        self.assertEqual(device._backend.model_string, "EMU-250")
        (session,) = self.quietly(engine.list_sessions)
        self.assertEqual((session.manual, session.record_count), (True, 59))
        records = self.quietly(engine.download_session, session)
        self.assertEqual(sum(record["spo2"] is not None for record in records), 14)

    def test_a_silent_port_fails_the_probe(self):
        device, _ = self.connect(faults="silent")
        self.assertIsNone(device._backend.model_string)

    def test_a_bad_checksum_fails_the_probe(self):
        device, _ = self.connect(faults="badsum")
        self.assertIsNone(device._backend.model_string)

    def test_a_protocol_b_device_is_refused_not_misdetected(self):
        """po300b: a real PO-300 owner's unit answered only Smart Device Assistant, not SpO2
        Assistant (CMS50_COMPATIBILITY.md finding 6); this is that guess, emulated far enough to
        prove the probe-and-refuse path (T-105, detection only) over a real compiled binary and a
        pseudo-terminal, not just the Python-level fakes in test_serial_port.py."""
        link = os.path.join(self.tmp, "ttyACM-emu")
        simulator = subprocess.Popen([self.binary, link, "po300b"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(simulator.stdout.close)
        self.addCleanup(simulator.wait)
        self.addCleanup(simulator.kill)
        simulator.stdout.readline()
        device = PulsoxHidDevice(device_path=link)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as context:
                device.connect()
        self.assertIn("CMS50F", str(context.exception))
        self.assertIn("protocol B", str(context.exception))


if __name__ == "__main__":
    unittest.main()
