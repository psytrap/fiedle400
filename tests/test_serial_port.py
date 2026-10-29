"""Mock-hardware tests for the USB-serial transport and model detection (T-101, T-104).

Nobody on the project owns a serial model, so the device here is the same FakeOximeter that
replays the PO-400's recorded replies (tests/hwsim.py). SpO2 Assistant sends the PO-400's
command frames over serial unchanged (PROTOCOL.md §5), which is what makes that a fair
stand-in. The fake port hands the replies over in small pieces with a quiet gap between
replies, so these tests also prove SerialBackend puts reports back together from a byte
stream. They cannot prove how a real PO-250/PO-300 answers (T-102).
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

try:  # POSIX only; the Windows CI job skips the pty test
    import pty
    import termios
except ImportError:
    pty = termios = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import scrub_env, FakeOximeter, Trace, VirtualClock, make_fake_hid_module  # noqa: E402
import test_hwsim_realtrace as rt  # noqa: E402

from fiedle400 import cli, protocol, serial_port  # noqa: E402
from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice, _uevent_matches  # noqa: E402


class FakeSerialPort:
    """A serial port wired to a FakeOximeter: writes go in, replies come out `chunk` bytes at a time.

    Replies are one continuous byte stream, cut wherever `chunk` falls, as a UART delivers
    them. A read returns nothing only once everything sent so far has been read.
    """

    def __init__(self, fake: FakeOximeter, chunk: int = 7):
        self.fake = fake
        self.chunk = chunk
        self.written = []
        self.closed = False
        self._stream = b""

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        self.fake.handle_out(data)
        return len(data)

    def read(self, n: int) -> bytes:
        while len(self._stream) < n:
            rep = self.fake.poll()
            if rep is None:
                break
            self._stream += bytes(rep)
        k = min(n, self.chunk)
        out, self._stream = self._stream[:k], self._stream[k:]
        return out

    def close(self) -> None:
        self.closed = True


MODEL_REPLY = bytes.fromhex("f135304620202020203c") + bytes(54)  # the PO-400's real "50F" answer


def probed_trace() -> Trace:
    """The PO-400 trace plus one more unlock and `81 01` exchange: the connect probe asks once
    before the commands the trace recorded."""
    t = Trace.from_json(rt.FIXTURE)
    t.add(protocol.Commands.unlock_handshake(), [])
    t.add(protocol.Commands.build_hid(0x81, [0x01]), [MODEL_REPLY])
    return t


class SerialCase(unittest.TestCase):
    chunk = 7

    def setUp(self):
        self.fake = FakeOximeter(probed_trace(), strict=True)
        self.port = FakeSerialPort(self.fake, chunk=self.chunk)
        for p in (
            mock.patch.object(serial_port, "open_port", lambda path: self.port),
            mock.patch.object(serial_port, "find_serial_candidates",
                              lambda: [("/dev/ttyUSB0", "10C4", "EA60")]),
            mock.patch("fiedle400.engine.device.SIMULATED_DEVICE_ACTIVE", True),
            VirtualClock().patch(),
            mock.patch.object(serial_port, "time", VirtualClock()),
        ):
            p.start()
            self.addCleanup(p.stop)

    def connect(self) -> SerialDeviceEngine:
        dev = PulsoxHidDevice(backend="serial")
        dev.connect()
        self.addCleanup(dev.close)
        return SerialDeviceEngine(dev)

    def assert_fully_answered(self):
        self.assertEqual([r.hex()[:24] for r in self.fake.unmatched], [])
        self.assertEqual(self.fake.destructive, [])


class TestUnpadReport(unittest.TestCase):
    def test_framed_command_loses_its_0x80_padding(self):
        rep = protocol.Commands.build_hid(0x81, [0x01])
        self.assertEqual(len(rep), 64)
        self.assertEqual(serial_port.unpad_report(rep), bytes([0x7D, 0x81, 0x81, 0x01]))

    def test_unlock_keeps_its_inner_0x80_bytes(self):
        out = serial_port.unpad_report(protocol.Commands.unlock_handshake())
        self.assertEqual(out[-3:], bytes([0x7D, 0x81, 0xA2]))
        self.assertIn(bytes([0x80] * 6), out)

    def test_bare_command_keeps_its_checksum(self):
        cmd = bytes.fromhex("9d7f7f7f7f000019")
        self.assertEqual(serial_port.unpad_report(cmd + bytes(56)), cmd)

    def test_a_zero_checksum_is_kept(self):
        # 0x80 alone sums to 0 mod 128, so its checksum byte is 0x00 and must not be cut.
        self.assertEqual(serial_port.unpad_report(bytes([0x80]) + bytes(63)), bytes([0x80, 0x00]))

    def test_serial_paths_are_recognised(self):
        for p in ("/dev/ttyUSB0", "/dev/ttyACM1", "COM3", "/dev/cu.SLAB_USBtoUART"):
            self.assertTrue(serial_port.is_serial_path(p), p)
        for p in (None, "/dev/hidraw0", "fake-hid-path", "COMPUTER"):
            self.assertFalse(serial_port.is_serial_path(p), p)


class TestDiscovery(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "builds a symlinked sysfs tree")
    def test_linux_finds_a_cp210x_tty_and_skips_others(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        tty_root = os.path.join(tmp, "class", "tty")
        for node, vid, pid in (("ttyUSB0", "10c4", "ea60"), ("ttyUSB1", "0403", "6001")):
            usb = os.path.join(tmp, "devices", node + "-usb")
            iface = os.path.join(usb, "1-1:1.0", node)
            os.makedirs(iface)
            for name, val in (("idVendor", vid), ("idProduct", pid)):
                with open(os.path.join(usb, name), "w") as fh:
                    fh.write(val + "\n")
            os.makedirs(os.path.join(tty_root, node))
            os.symlink(iface, os.path.join(tty_root, node, "device"))
        with mock.patch.object(serial_port, "SYSFS_TTY_ROOT", tty_root):
            self.assertEqual(serial_port._linux_candidates(), [("/dev/ttyUSB0", "10C4", "EA60")])

    def test_windows_reads_the_port_name_from_the_registry(self):
        tree = {r"SYSTEM\CurrentControlSet\Enum\USB\VID_0483&PID_5740": {"5&1a2b": "COM7"}}

        def open_key(root, path):
            if isinstance(root, dict):
                inst = path.split("\\")[0]
                if inst not in root:
                    raise OSError(path)
                return {"PortName": root[inst]}
            if path not in tree:
                raise OSError(path)
            return tree[path]

        def enum_key(key, i):
            names = list(key)
            if i >= len(names):
                raise OSError("no more")
            return names[i]

        winreg = types.SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", OpenKey=open_key, EnumKey=enum_key,
                                       QueryValueEx=lambda key, name: (key[name], 1))
        self.assertEqual(serial_port._windows_candidates(winreg), [("COM7", "0483", "5740")])

    def test_windows_skips_remembered_ports_that_are_not_present(self):
        """The USB Enum keys also keep devices unplugged long ago; SERIALCOMM lists what exists now."""
        tree = {r"SYSTEM\CurrentControlSet\Enum\USB\VID_10C4&PID_EA60": {"old": "COM4", "new": "COM9"}}
        present = [("\\Device\\Silabser0", "COM9", 1)]

        def open_key(root, path):
            if path == r"HARDWARE\DEVICEMAP\SERIALCOMM":
                return "SERIALCOMM"
            if isinstance(root, dict):
                return {"PortName": root[path.split("\\")[0]]}
            if path not in tree:
                raise OSError(path)
            return tree[path]

        def enum_key(key, i):
            if i >= len(key):
                raise OSError("no more")
            return list(key)[i]

        def enum_value(key, i):
            if i >= len(present):
                raise OSError("no more")
            return present[i]

        winreg = types.SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", OpenKey=open_key, EnumKey=enum_key,
                                       EnumValue=enum_value, QueryValueEx=lambda key, name: (key[name], 1))
        self.assertEqual(serial_port._windows_candidates(winreg), [("COM9", "10C4", "EA60")])

    def test_both_spo2_assistant_hid_ids_match(self):
        self.assertTrue(_uevent_matches("HID_ID=0003:000028E9:0000028A\n"))
        self.assertTrue(_uevent_matches("HID_ID=0003:00000483:00005751\n"))
        self.assertFalse(_uevent_matches("HID_ID=0003:0000046D:0000C52B\n"))


@unittest.skipUnless(pty is not None and hasattr(pty, "openpty"), "needs a pseudo-terminal")
class TestPosixPort(unittest.TestCase):
    """The real termios setup, against a pty instead of a USB serial adapter."""

    def test_raw_115200_and_bytes_pass_unchanged(self):
        master, slave = pty.openpty()
        path = os.ttyname(slave)
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        port = serial_port._PosixPort(path)
        self.addCleanup(port.close)
        attrs = termios.tcgetattr(port.fd)
        self.assertEqual(attrs[4], termios.B115200)
        self.assertEqual(attrs[3] & termios.ICANON, 0)
        self.assertEqual(attrs[3] & termios.ECHO, 0)
        self.assertEqual(port.read(64), b"")  # non-blocking: nothing there yet
        frame = bytes([0x7D, 0x81, 0xA7, 0x80, 0x0D, 0x0A, 0x11])
        port.write(frame)
        self.assertEqual(os.read(master, 64), frame)
        os.write(master, bytes([0xF0, 0x70, 0x0D, 0x00]))
        got = b""
        for _ in range(100):
            got += port.read(64)
            if len(got) >= 4:
                break
        self.assertEqual(got, bytes([0xF0, 0x70, 0x0D, 0x00]))


class TestReviewFixes(unittest.TestCase):
    """Defects found in the 0036 code review (2026-10-29), each pinned by a test."""

    def test_posix_write_retries_short_writes_and_eagain(self):
        port = serial_port._PosixPort.__new__(serial_port._PosixPort)
        port.fd = 99
        calls = []

        def fake_write(fd, view):
            calls.append(bytes(view))
            if len(calls) == 1:
                return 3                      # short write
            if len(calls) == 2:
                raise BlockingIOError()       # output buffer full
            return len(view)

        with mock.patch.object(serial_port.os, "write", fake_write), \
                mock.patch.object(serial_port, "time", VirtualClock()):
            self.assertEqual(port.write(b"0123456789"), 10)
        self.assertEqual(calls, [b"0123456789", b"3456789", b"3456789"])

    def test_probe_does_not_hang_on_a_device_that_keeps_streaming(self):
        backend = mock.MagicMock()
        backend.read_report.side_effect = [MODEL_REPLY] + [bytes([0xEB, 0x01, 0x02])] * 1000
        with mock.patch.object(serial_port, "time", VirtualClock()):
            self.assertEqual(serial_port.probe_model(backend), "50F")
        self.assertLess(backend.read_report.call_count, 20)

    def test_hid_without_a_path_opens_the_ids_it_enumerated(self):
        from fiedle400 import hid_driver
        opened = []

        class Dev:
            def open(self, vid, pid):
                opened.append((vid, pid))

            def set_nonblocking(self, flag):
                pass

        def enumerate_(vid, pid):
            if (vid, pid) == (0x0483, 0x5751):
                return [{"vendor_id": vid, "product_id": pid}]  # no "path" key
            return []

        hid = types.SimpleNamespace(enumerate=enumerate_, device=Dev)
        with mock.patch.dict(sys.modules, {"hid": hid}):
            path = hid_driver.HidBackend().connect()
        self.assertEqual(opened, [(0x0483, 0x5751)])
        self.assertEqual(path, "hid:0483:5751")


class TestSerialFlows(SerialCase):
    def test_sessions_and_download_over_serial(self):
        engine = self.connect()
        sessions = engine.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].record_count, 214)
        with contextlib.redirect_stdout(io.StringIO()):
            records = engine.download_session(sessions[0])
        self.assertEqual(len(records), 214)
        self.assert_fully_answered()

    def test_no_padding_reaches_the_line(self):
        engine = self.connect()
        engine.list_sessions()
        self.assertTrue(self.port.written)
        for data in self.port.written:
            self.assertLess(len(data), 64)
            if data[:2] == b"\x7d\x81":
                self.assertNotEqual(data[-1], 0x80)

    def test_model_string_comes_from_the_device(self):
        engine = self.connect()
        info = engine.read_device_info()["device_info"]
        self.assertEqual(info.hardware_id, "50F")


class TestSerialFlowsByteByByte(TestSerialFlows):
    """The same flows when the port hands over one byte per read."""
    chunk = 1


def run_cli(argv, fake_module=None):
    out, err = io.StringIO(), io.StringIO()
    mods = {"hid": fake_module} if fake_module is not None else {}
    with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        scrub_env()
        try:
            cli.main(argv)
            rc = 0
        except SystemExit as e:
            rc = e.code or 0
    return rc, out.getvalue(), err.getvalue()


class TestCliOverSerial(SerialCase):
    def test_a_serial_device_path_picks_the_serial_backend(self):
        rc, out, err = run_cli(["sessions", "--device", "/dev/ttyUSB0"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("214", out)

    def test_falls_back_to_serial_when_no_hid_device_is_found(self):
        no_hid = make_fake_hid_module(FakeOximeter(rt.real_trace()), present=False)
        with mock.patch("fiedle400.hid_driver.resolve_default_backend", return_value="hid"):
            rc, out, err = run_cli(["sessions"], no_hid)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("/dev/ttyUSB0", out)

    def test_info_names_the_model_transport_and_usb_id(self):
        rc, out, err = run_cli(["info", "--backend", "serial"])
        self.assertEqual(rc, 0, out + err)
        self.assertRegex(out, r"Detected Model\s*: Pulox PO-400  \(USB serial, 10C4:EA60\)")
        self.assertIn("USB serial (115200 baud)", out)

    def test_clear_is_refused_on_a_serial_device(self):
        rc, out, err = run_cli(["clear", "--backend", "serial", "--yes"])
        self.assertEqual(rc, 1)
        self.assertIn("only enabled for the PO-400", out)
        self.assertEqual(self.fake.destructive, [])
        # Only the connect probe went out (unlock, model query); no erase command.
        self.assertEqual(self.fake.opcodes_sent(), [0xA7, 0x81])


class ScriptedPort:
    """A serial port that answers every write with fixed bytes (or nothing)."""

    def __init__(self, reply: bytes = b""):
        self.reply = reply
        self.written = []
        self.closed = False
        self._out = b""

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        if data[-2:] == b"\x81\x01":  # the model query
            self._out += self.reply
        return len(data)

    def read(self, n: int) -> bytes:
        out, self._out = self._out[:n], self._out[n:]
        return out

    def close(self) -> None:
        self.closed = True


class TestProbe(unittest.TestCase):
    """The connect probe (psytrap, 2026-10-29): a port is only used if it answers like an oximeter."""

    def setUp(self):
        self.clock = VirtualClock()
        p = mock.patch.object(serial_port, "time", self.clock)
        p.start()
        self.addCleanup(p.stop)

    def connect(self, ports, candidates, device=None):
        out = io.StringIO()
        with mock.patch.object(serial_port, "open_port", lambda path: ports[path]), \
                mock.patch.object(serial_port, "find_serial_candidates", lambda: candidates), \
                contextlib.redirect_stdout(out):
            b = serial_port.SerialBackend(device)
            try:
                path = b.connect()
            except RuntimeError as e:
                return None, b, str(e) + out.getvalue()
        return path, b, out.getvalue()

    def test_valid_model_frame(self):
        self.assertEqual(serial_port.find_model_frame(b"\x00" + MODEL_REPLY), "50F")
        bad = bytearray(MODEL_REPLY)
        bad[9] ^= 1
        self.assertIsNone(serial_port.find_model_frame(bytes(bad)))
        self.assertIsNone(serial_port.find_model_frame(bytes.fromhex("f1010203040506070809")))  # not ASCII

    def test_silent_garbage_and_bad_checksum_ports_are_skipped(self):
        bad = bytearray(MODEL_REPLY)
        bad[9] ^= 1
        ports = {"/dev/ttyUSB0": ScriptedPort(), "/dev/ttyUSB1": ScriptedPort(b"hello world\r\n" * 5),
                 "/dev/ttyUSB2": ScriptedPort(bytes(bad)), "/dev/ttyUSB3": ScriptedPort(MODEL_REPLY)}
        cands = [(p, "10C4", "EA60") for p in sorted(ports)]
        path, b, out = self.connect(ports, cands)
        self.assertEqual(path, "/dev/ttyUSB3")
        self.assertEqual(b.model_string, "50F")
        self.assertEqual(out.count("not an oximeter, skipped"), 3)
        for p in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"):
            self.assertTrue(ports[p].closed, p)
        self.assertFalse(ports["/dev/ttyUSB3"].closed)
        # What a foreign device received: the unlock and the model query, nothing else.
        self.assertEqual([w[2] for w in ports["/dev/ttyUSB0"].written], [0xA7, 0x81])

    def test_several_answering_ports_use_the_first_and_say_so(self):
        ports = {"/dev/ttyUSB0": ScriptedPort(MODEL_REPLY), "/dev/ttyACM0": ScriptedPort(MODEL_REPLY)}
        path, b, out = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60"), ("/dev/ttyACM0", "0483", "5740")])
        self.assertEqual(path, "/dev/ttyUSB0")
        self.assertIn("Pick another with --device", out)
        self.assertTrue(ports["/dev/ttyACM0"].closed)

    def test_no_answering_port_is_a_clear_error(self):
        ports = {"/dev/ttyUSB0": ScriptedPort()}
        path, b, msg = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60")])
        self.assertIsNone(path)
        self.assertIn("No oximeter answered", msg)
        self.assertIn("/dev/ttyUSB0 (10C4:EA60) did not answer like an oximeter", msg)

    def test_an_explicit_port_is_used_with_a_warning_if_silent(self):
        ports = {"/dev/ttyUSB5": ScriptedPort()}
        path, b, out = self.connect(ports, [], device="/dev/ttyUSB5")
        self.assertEqual(path, "/dev/ttyUSB5")
        self.assertIn("continuing because you chose it", out)

    def test_generic_stm32_hid_id_that_does_not_answer_is_rejected(self):
        dev = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        backend.read_report.return_value = None
        dev._backend = backend
        with self.assertRaises(RuntimeError) as ctx:
            dev.connect()
        self.assertIn("did not answer like an oximeter", str(ctx.exception))
        backend.close.assert_called_once()

    def test_generic_stm32_hid_id_that_answers_is_kept(self):
        dev = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        backend.read_report.side_effect = [MODEL_REPLY, None]
        dev._backend = backend
        self.assertEqual(dev.connect(), "hid-path")
        backend.close.assert_not_called()

    def test_the_po400_hid_id_is_not_probed(self):
        dev = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "28E9", "pid_hex": "028A"}
        dev._backend = backend
        dev.connect()
        backend.write_report.assert_not_called()


class TestUnknownModel(unittest.TestCase):
    def test_describe_model_never_guesses(self):
        self.assertEqual(protocol.describe_model("50F"), "Pulox PO-400")
        self.assertIn('"50D"', protocol.describe_model("50D"))
        self.assertIn("not reported", protocol.describe_model(None))

    def test_unknown_model_asks_for_the_info_output(self):
        dev = mock.MagicMock(backend_name="hid")
        dev.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        lines = cli._model_lines(dev, "50X")
        self.assertIn("0483:5751", lines[0])
        self.assertIn("fiedle400 info", lines[1])
        self.assertFalse(cli._erase_supported(dev))

    def test_po400_usb_id_keeps_erase(self):
        dev = mock.MagicMock(backend_name="hidraw")
        dev.get_descriptor_info.return_value = {"vid_hex": "28E9", "pid_hex": "028A"}
        self.assertTrue(cli._erase_supported(dev))
        self.assertEqual(cli._model_lines(dev, "50F"), ["Pulox PO-400  (USB HID, 28E9:028A)"])


if __name__ == "__main__":
    unittest.main()
