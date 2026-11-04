"""The Arduino serial emulator (hardware/serial-emulator/) against fiedle400's real serial code.

The emulator's core (emulator.h) is built for the PC (host_sim.cpp) and served on a
pseudo-terminal, so these tests run SerialBackend over real termios, as on a USB-serial port.
They prove the sketch answers like the mock tests' FakeOximeter (protocol C) and like the
2014 protocol-B capture (PO-250, T-105); how a real PO-250/PO-300 answers is still open
(T-102, T-105). Skipped without a C++ compiler or pty.
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

from fiedle400 import serial_engine  # noqa: E402
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
        return device, serial_engine.make_engine(device)

    def quietly(self, function, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args)

    def test_po400_probe_lists_and_downloads_the_214_second_auto_recording(self):
        device, engine = self.connect()
        self.assertEqual(device._backend.model_string, "50F")
        (session,) = self.quietly(engine.list_sessions)
        self.assertEqual((session.manual, session.record_count), (False, 214))
        self.assertEqual(len(self.quietly(engine.download_session, session)), 214)

    def test_po250_speaks_protocol_b_and_downloads_like_the_replay_test(self):
        """The default model (no jumper): matches tests/test_protocol_b.py's capture replay."""
        device, engine = self.connect("po250")
        self.assertEqual((device.protocol, device.model_string), ("cms50f37", "EMU-250"))
        (session,) = self.quietly(engine.list_sessions)
        self.assertEqual((session.record_count, session.timestamp.isoformat()), (20904, "2014-08-03T03:18:48"))
        records = self.quietly(engine.download_session, session)
        self.assertEqual(len(records), 8202)
        self.assertEqual(len(engine.download_warnings), 1)

    def test_po300_is_on_a_jumper_and_speaks_protocol_c(self):
        device, engine = self.connect("po300")
        self.assertEqual((device.protocol, device.model_string), ("po400", "EMU-300"))
        self.assertEqual(len(self.quietly(engine.list_sessions)), 1)

    def test_a_silent_port_fails_the_probe(self):
        device, _ = self.connect(faults="silent")
        self.assertIsNone(device._backend.model_string)

    def test_a_bad_checksum_fails_the_probe(self):
        device, _ = self.connect(faults="badsum")
        self.assertIsNone(device._backend.model_string)

    def test_a_cms50f_is_refused_by_its_model_string(self):
        """cms50f: the same protocol and data as the PO-250, but the device names itself
        CMS50F, so fiedle400 refuses it (T-105) -- over a real compiled binary and a
        pseudo-terminal, not just the Python-level fakes in test_protocol_b.py."""
        link = os.path.join(self.tmp, "ttyACM-emu")
        simulator = subprocess.Popen([self.binary, link, "cms50f"], stdout=subprocess.PIPE,
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
        self.assertIn("only for the PO-250", str(context.exception))

if __name__ == "__main__":
    unittest.main()
