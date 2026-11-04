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
from hwsim import scrub_environment, FakeOximeter, Trace, VirtualClock, make_fake_hid_module  # noqa: E402
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
        self.fake.handle_output(data)
        return len(data)

    def read(self, size: int) -> bytes:
        while len(self._stream) < size:
            report = self.fake.poll()
            if report is None:
                break
            self._stream += bytes(report)
        k = min(size, self.chunk)
        output, self._stream = self._stream[:k], self._stream[k:]
        return output

    def close(self) -> None:
        self.closed = True


MODEL_REPLY = bytes.fromhex("f135304620202020203c") + bytes(54)  # the PO-400's real "50F" answer
# "EMU-300" (the serial emulator's placeholder model string, T-104/T-101): its checksum byte,
# 0x38 ('8'), is alphanumeric, unlike "50F"'s ('<', filtered out) -- it would leak into
# info.hardware_id if the model slice ever grew back to include the checksum byte.
EMU300_MODEL_REPLY = bytes.fromhex("f1454d552d3330302038") + bytes(54)


def probed_trace(model_reply: bytes = MODEL_REPLY) -> Trace:
    """The PO-400 trace plus one more unlock and `81 01` exchange: the connect probe asks once
    before the commands the trace recorded."""
    trace = Trace.from_json(rt.FIXTURE)
    trace.add(protocol.Commands.unlock_handshake(), [])
    trace.add(protocol.Commands.build_hid(0x81, [0x01]), [model_reply])
    return trace


class SerialCase(unittest.TestCase):
    chunk = 7
    model_reply = MODEL_REPLY

    def setUp(self):
        self.fake = FakeOximeter(probed_trace(self.model_reply), strict=True)
        self.port = FakeSerialPort(self.fake, chunk=self.chunk)
        for patcher in (
            mock.patch.object(serial_port, "open_port", lambda path: self.port),
            mock.patch.object(serial_port, "find_serial_candidates",
                              lambda: [("/dev/ttyUSB0", "10C4", "EA60")]),
            mock.patch("fiedle400.engine.device.SIMULATED_DEVICE_ACTIVE", True),
            VirtualClock().patch(),
            mock.patch.object(serial_port, "time", VirtualClock()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def connect(self) -> SerialDeviceEngine:
        device = PulsoxHidDevice(backend="serial")
        device.connect()
        self.addCleanup(device.close)
        return SerialDeviceEngine(device)

    def assert_fully_answered(self):
        self.assertEqual([report.hex()[:24] for report in self.fake.unmatched], [])
        self.assertEqual(self.fake.destructive, [])


class TestUnpadReport(unittest.TestCase):
    def test_framed_command_loses_its_0x80_padding(self):
        report = protocol.Commands.build_hid(0x81, [0x01])
        self.assertEqual(len(report), 64)
        self.assertEqual(serial_port.unpad_report(report), bytes([0x7D, 0x81, 0x81, 0x01]))

    def test_unlock_keeps_its_inner_0x80_bytes(self):
        output = serial_port.unpad_report(protocol.Commands.unlock_handshake())
        self.assertEqual(output[-3:], bytes([0x7D, 0x81, 0xA2]))
        self.assertIn(bytes([0x80] * 6), output)

    def test_bare_command_keeps_its_checksum(self):
        command = bytes.fromhex("9d7f7f7f7f000019")
        self.assertEqual(serial_port.unpad_report(command + bytes(56)), command)

    def test_a_zero_checksum_is_kept(self):
        # 0x80 alone sums to 0 mod 128, so its checksum byte is 0x00 and must not be cut.
        self.assertEqual(serial_port.unpad_report(bytes([0x80]) + bytes(63)), bytes([0x80, 0x00]))

    def test_serial_paths_are_recognised(self):
        for path in ("/dev/ttyUSB0", "/dev/ttyACM1", "COM3", "/dev/cu.SLAB_USBtoUART"):
            self.assertTrue(serial_port.is_serial_path(path), path)
        for path in (None, "/dev/hidraw0", "fake-hid-path", "COMPUTER"):
            self.assertFalse(serial_port.is_serial_path(path), path)


class TestDiscovery(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "builds a symlinked sysfs tree")
    def test_linux_finds_a_cp210x_tty_and_skips_others(self):
        temporary_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temporary_directory)
        tty_root = os.path.join(temporary_directory, "class", "tty")
        for node, vid, pid in (("ttyUSB0", "10c4", "ea60"), ("ttyUSB1", "0403", "6001")):
            usb = os.path.join(temporary_directory, "devices", node + "-usb")
            iface = os.path.join(usb, "1-1:1.0", node)
            os.makedirs(iface)
            for name, value in (("idVendor", vid), ("idProduct", pid)):
                with open(os.path.join(usb, name), "w") as file:
                    file.write(value + "\n")
            os.makedirs(os.path.join(tty_root, node))
            os.symlink(iface, os.path.join(tty_root, node, "device"))
        with mock.patch.object(serial_port, "SYSFS_TTY_ROOT", tty_root):
            self.assertEqual(serial_port._linux_candidates(), [("/dev/ttyUSB0", "10C4", "EA60")])

    def test_windows_reads_the_port_name_from_the_registry(self):
        tree = {r"SYSTEM\CurrentControlSet\Enum\USB\VID_0483&PID_5740": {"5&1a2b": "COM7"}}

        def open_key(root, path):
            if isinstance(root, dict):
                instance = path.split("\\")[0]
                if instance not in root:
                    raise OSError(path)
                return {"PortName": root[instance]}
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
        attributes = termios.tcgetattr(port.file_descriptor)
        self.assertEqual(attributes[4], termios.B115200)
        self.assertEqual(attributes[3] & termios.ICANON, 0)
        self.assertEqual(attributes[3] & termios.ECHO, 0)
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
        port.file_descriptor = 99
        calls = []

        def fake_write(file_descriptor, view):
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


class TestModelStringChecksumByteIsNotPartOfTheModel(SerialCase):
    """Found testing against the real serial emulator (T-102): the model slice used to be one
    byte too wide and included the checksum byte, invisible with "50F" (its checksum filters
    out as non-alphanumeric) but not with a model string whose checksum happens to be alnum."""
    model_reply = EMU300_MODEL_REPLY

    def test_model_string_comes_from_the_device(self):
        engine = self.connect()
        info = engine.read_device_info()["device_info"]
        self.assertEqual(info.hardware_id, "EMU-300")


class TestSerialFlowsByteByByte(TestSerialFlows):
    """The same flows when the port hands over one byte per read."""
    chunk = 1


def run_cli(argv, fake_module=None):
    output, error_output = io.StringIO(), io.StringIO()
    mods = {"hid": fake_module} if fake_module is not None else {}
    with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
        scrub_environment()
        try:
            cli.main(argv)
            exit_code = 0
        except SystemExit as error:
            exit_code = error.code or 0
    return exit_code, output.getvalue(), error_output.getvalue()


class TestCliOverSerial(SerialCase):
    def test_a_serial_device_path_picks_the_serial_backend(self):
        exit_code, output, error_output = run_cli(["sessions", "--device", "/dev/ttyUSB0"])
        self.assertEqual(exit_code, 0, output + error_output)
        self.assertIn("214", output)

    def test_falls_back_to_serial_when_no_hid_device_is_found(self):
        no_hid = make_fake_hid_module(FakeOximeter(rt.real_trace()), present=False)
        with mock.patch("fiedle400.hid_driver.resolve_default_backend", return_value="hid"):
            exit_code, output, error_output = run_cli(["sessions"], no_hid)
        self.assertEqual(exit_code, 0, output + error_output)
        self.assertIn("/dev/ttyUSB0", output)

    def test_info_names_the_model_transport_and_usb_id(self):
        exit_code, output, error_output = run_cli(["info", "--backend", "serial"])
        self.assertEqual(exit_code, 0, output + error_output)
        self.assertRegex(output, r"Detected Model\s*: Pulox PO-400  \(USB serial, 10C4:EA60\)")
        self.assertIn("USB serial (115200 baud)", output)

    def test_clear_is_refused_on_a_serial_device(self):
        exit_code, output, error_output = run_cli(["clear", "--backend", "serial", "--yes"])
        self.assertEqual(exit_code, 1)
        self.assertIn("only enabled for the PO-400", output)
        self.assertEqual(self.fake.destructive, [])
        # Only the connect probe went out (unlock, model query); no erase command.
        self.assertEqual(self.fake.opcodes_sent(), [0xA7, 0x81])


class ScriptedPort:
    """A serial port that answers every write with fixed bytes (or nothing)."""

    def __init__(self, reply: bytes = b""):
        self.reply = reply
        self.written = []
        self.closed = False
        self._output = b""

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        if data[-2:] == b"\x81\x01":  # the model query
            self._output += self.reply
        return len(data)

    def read(self, size: int) -> bytes:
        output, self._output = self._output[:size], self._output[size:]
        return output

    def close(self) -> None:
        self.closed = True


class Cms50f37Port:
    """A serial port that answers protocol B's discovery (PROTOCOL_B.md §1, T-105): `0C 80` to
    the hello (`A7`/`A2`), a `0x10` frame to the user count (`AD`) and two `0x02` frames to the
    model query (`A8`), every byte after the code with bit 7 set. Silent to the PO-x00 model
    query (`81 01`), as a protocol-B device is."""

    def __init__(self, model: str = "CMS50F"):
        self.model = model
        self.written = []
        self.closed = False
        self._output = b""

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        if len(data) == 9 and tuple(data[:2]) == (0x7D, 0x81):
            if data[2] in (0xA7, 0xA2):
                self._output += b"\x0c\x80"
            elif data[2] == 0xAD:
                self._output += b"\x10\x80\x81"
            elif data[2] == 0xA8:
                name = self.model.encode("ascii").ljust(12, b" ")
                self._output += (bytes([0x02, 0x80, 0x80]) + bytes(byte | 0x80 for byte in name[:6])
                                 + bytes([0x02, 0x80, 0x81]) + bytes(byte | 0x80 for byte in name[6:]))
        return len(data)

    def read(self, size: int) -> bytes:
        output, self._output = self._output[:size], self._output[size:]
        return output

    def close(self) -> None:
        self.closed = True


class TestProbe(unittest.TestCase):
    """The connect probe (psytrap, 2026-10-29): a port is only used if it answers like an oximeter."""

    def setUp(self):
        self.clock = VirtualClock()
        patcher = mock.patch.object(serial_port, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self, ports, candidates, device=None):
        output = io.StringIO()
        with mock.patch.object(serial_port, "open_port", lambda path: ports[path]), \
                mock.patch.object(serial_port, "find_serial_candidates", lambda: candidates), \
                contextlib.redirect_stdout(output):
            backend = serial_port.SerialBackend(device)
            try:
                path = backend.connect()
            except RuntimeError as error:
                return None, backend, str(error) + output.getvalue()
        return path, backend, output.getvalue()

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
        candidates = [(port_path, "10C4", "EA60") for port_path in sorted(ports)]
        path, backend, output = self.connect(ports, candidates)
        self.assertEqual(path, "/dev/ttyUSB3")
        self.assertEqual(backend.model_string, "50F")
        self.assertEqual(output.count("not an oximeter, skipped"), 3)
        for port_path in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"):
            self.assertTrue(ports[port_path].closed, port_path)
        self.assertFalse(ports["/dev/ttyUSB3"].closed)
        # What a foreign device received: the PO-x00 unlock and model query, then the
        # protocol-B discovery (flush, hello x2, user count, model query). Never AA or AE.
        self.assertEqual([write[2] for write in ports["/dev/ttyUSB0"].written],
                          [0xA7, 0x81, 0x80, 0xA7, 0xA2, 0xAD, 0xA8])

    def test_several_answering_ports_use_the_first_and_say_so(self):
        ports = {"/dev/ttyUSB0": ScriptedPort(MODEL_REPLY), "/dev/ttyACM0": ScriptedPort(MODEL_REPLY)}
        path, backend, output = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60"), ("/dev/ttyACM0", "0483", "5740")])
        self.assertEqual(path, "/dev/ttyUSB0")
        self.assertIn("Pick another with --device", output)
        self.assertTrue(ports["/dev/ttyACM0"].closed)

    def test_no_answering_port_is_a_clear_error(self):
        ports = {"/dev/ttyUSB0": ScriptedPort()}
        path, backend, message = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60")])
        self.assertIsNone(path)
        self.assertIn("No oximeter answered", message)
        self.assertIn("/dev/ttyUSB0 (10C4:EA60) did not answer like an oximeter", message)

    def test_an_explicit_port_is_used_with_a_warning_if_silent(self):
        ports = {"/dev/ttyUSB5": ScriptedPort()}
        path, backend, output = self.connect(ports, [], device="/dev/ttyUSB5")
        self.assertEqual(path, "/dev/ttyUSB5")
        self.assertIn("continuing because you chose it", output)

    def test_explicit_device_speaking_protocol_b_is_refused_not_used(self):
        ports = {"/dev/ttyUSB0": Cms50f37Port("CMS50F")}
        path, backend, message = self.connect(ports, [], device="/dev/ttyUSB0")
        self.assertIsNone(path)
        self.assertIn("CMS50F", message)
        self.assertIn("protocol B", message)
        self.assertIn("only for the PO-250", message)
        self.assertEqual(backend.protocol, "cms50f37")

    def test_autoscan_with_only_a_protocol_b_candidate_is_refused_by_name(self):
        ports = {"/dev/ttyUSB0": Cms50f37Port("CMS50I")}
        path, backend, message = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60")])
        self.assertIsNone(path)
        self.assertIn("CMS50I", message)
        self.assertIn("protocol B", message)
        self.assertTrue(ports["/dev/ttyUSB0"].closed)

    def test_autoscan_prefers_protocol_c_and_skips_protocol_b_candidate(self):
        ports = {"/dev/ttyUSB0": Cms50f37Port("CMS50F"), "/dev/ttyUSB1": ScriptedPort(MODEL_REPLY)}
        path, backend, output = self.connect(ports, [("/dev/ttyUSB0", "10C4", "EA60"),
                                             ("/dev/ttyUSB1", "10C4", "EA60")])
        self.assertEqual(path, "/dev/ttyUSB1")
        self.assertEqual(backend.protocol, "po400")
        self.assertIn("found a CMS50F (protocol B, not supported), skipped", output)
        self.assertTrue(ports["/dev/ttyUSB0"].closed)

    def test_probe_cms50f37_reads_the_model_and_leaves_po400_probe_unaffected(self):
        port = Cms50f37Port("CMS50H")
        backend = serial_port.SerialBackend("/dev/ttyUSB0")
        with mock.patch.object(serial_port, "open_port", lambda path: port):
            backend._open("/dev/ttyUSB0")
        self.assertIsNone(serial_port.probe_model(backend))  # a protocol-B device never answers C
        self.assertEqual(serial_port.probe_cms50f37(backend), (True, "CMS50H"))

    def test_generic_stm32_hid_id_that_does_not_answer_is_rejected(self):
        device = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        backend.read_report.return_value = None
        device._backend = backend
        with self.assertRaises(RuntimeError) as context:
            device.connect()
        self.assertIn("did not answer like an oximeter", str(context.exception))
        backend.close.assert_called_once()

    def test_generic_stm32_hid_id_that_answers_is_kept(self):
        device = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        backend.read_report.side_effect = [MODEL_REPLY, None]
        device._backend = backend
        self.assertEqual(device.connect(), "hid-path")
        backend.close.assert_not_called()

    def test_the_po400_hid_id_is_not_probed(self):
        device = PulsoxHidDevice(backend="hid")
        backend = mock.MagicMock()
        backend.connect.return_value = "hid-path"
        backend.get_descriptor_info.return_value = {"vid_hex": "28E9", "pid_hex": "028A"}
        device._backend = backend
        device.connect()
        backend.write_report.assert_not_called()


class TestUnknownModel(unittest.TestCase):
    def test_describe_model_never_guesses(self):
        self.assertEqual(protocol.describe_model("50F"), "Pulox PO-400")
        self.assertIn('"50D"', protocol.describe_model("50D"))
        self.assertIn("not reported", protocol.describe_model(None))

    def test_unknown_model_asks_for_the_info_output(self):
        device = mock.MagicMock(backend_name="hid")
        device.get_descriptor_info.return_value = {"vid_hex": "0483", "pid_hex": "5751"}
        lines = cli._model_lines(device, "50X")
        self.assertIn("0483:5751", lines[0])
        self.assertIn("fiedle400 info", lines[1])
        self.assertFalse(cli._erase_supported(device))

    def test_po400_usb_id_keeps_erase(self):
        device = mock.MagicMock(backend_name="hidraw")
        device.get_descriptor_info.return_value = {"vid_hex": "28E9", "pid_hex": "028A"}
        self.assertTrue(cli._erase_supported(device))
        self.assertEqual(cli._model_lines(device, "50F"), ["Pulox PO-400  (USB HID, 28E9:028A)"])


if __name__ == "__main__":
    unittest.main()
