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
EMU_DIR = os.path.join(ROOT, "hardware", "serial-emulator")
sys.path.insert(0, EMU_DIR)
import make_trace  # noqa: E402

from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402

CXX = shutil.which("g++") or shutil.which("c++")


class TestTraceData(unittest.TestCase):
    def test_trace_data_h_matches_the_fixtures(self):
        with open(make_trace.OUT, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), make_trace.render(),
                             "run python3 hardware/serial-emulator/make_trace.py")


@unittest.skipUnless(CXX and sys.platform != "win32", "needs a C++ compiler and a pseudo-terminal")
class TestHostSim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.binary = os.path.join(cls.tmp, "host_sim")
        subprocess.run([CXX, "-O2", "-o", cls.binary, os.path.join(EMU_DIR, "host_sim.cpp")], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def connect(self, model="po400", faults="none"):
        link = os.path.join(self.tmp, "ttyACM-emu")
        sim = subprocess.Popen([self.binary, link, model, faults], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(sim.stdout.close)
        self.addCleanup(sim.wait)
        self.addCleanup(sim.kill)
        sim.stdout.readline()  # the link exists once this is printed
        dev = PulsoxHidDevice(dev_path=link)
        with contextlib.redirect_stdout(io.StringIO()):
            dev.connect()
        self.addCleanup(dev.close)
        return dev, SerialDeviceEngine(dev)

    def quietly(self, fn, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args)

    def test_po400_probe_lists_and_downloads_the_214_second_auto_recording(self):
        dev, engine = self.connect()
        self.assertEqual(dev._backend.model_string, "50F")
        (s,) = self.quietly(engine.list_sessions)
        self.assertEqual((s.manual, s.record_count), (False, 214))
        self.assertEqual(len(self.quietly(engine.download_session, s)), 214)

    def test_po250_has_only_the_manual_recording_and_a_placeholder_model(self):
        dev, engine = self.connect("po250")
        self.assertEqual(dev._backend.model_string, "EMU-250")
        (s,) = self.quietly(engine.list_sessions)
        self.assertEqual((s.manual, s.record_count), (True, 59))
        records = self.quietly(engine.download_session, s)
        self.assertEqual(sum(r["spo2"] is not None for r in records), 14)

    def test_a_silent_port_fails_the_probe(self):
        dev, _ = self.connect(faults="silent")
        self.assertIsNone(dev._backend.model_string)

    def test_a_bad_checksum_fails_the_probe(self):
        dev, _ = self.connect(faults="badsum")
        self.assertIsNone(dev._backend.model_string)

    def test_a_protocol_b_device_is_refused_not_misdetected(self):
        """po300b: a real PO-300 owner's unit answered only Smart Device Assistant, not SpO2
        Assistant (CMS50_COMPATIBILITY.md finding 6); this is that guess, emulated far enough to
        prove the probe-and-refuse path (T-105, detection only) over a real compiled binary and a
        pseudo-terminal, not just the Python-level fakes in test_serial_port.py."""
        link = os.path.join(self.tmp, "ttyACM-emu")
        sim = subprocess.Popen([self.binary, link, "po300b"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(sim.stdout.close)
        self.addCleanup(sim.wait)
        self.addCleanup(sim.kill)
        sim.stdout.readline()
        dev = PulsoxHidDevice(dev_path=link)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as ctx:
                dev.connect()
        self.assertIn("CMS50F", str(ctx.exception))
        self.assertIn("protocol B", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
