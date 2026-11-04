"""Mock tests for the PO-250 in protocol B (T-105): probe gate, engine, CLI.

The device here replays a real protocol-B download: SpO2 Assistant 2.x downloading a CMS50F with
firmware 3.7, captured in 2014 (tests/fixtures/cms50f37-download.trace.json, PROTOCOL_B.md §5.1).
The PO-250 speaks the same protocol (kaivol/pulox, CMS50_COMPATIBILITY.md finding 10), but its
own `A8` model string is unknown, so the fake answers `A8` with a chosen string or not at all.
The capture stops before the download ends: 8,202 of the 20,904 announced samples.
"""

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import VirtualClock, scrub_environment  # noqa: E402

from fiedle400 import cli, serial_engine, serial_port  # noqa: E402
from fiedle400.engine import Cms50F37Engine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402
from fiedle400.protocol import cms50f37 as protocol_b  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cms50f37-download.trace.json")
ANNOUNCED, RECEIVED = 20904, 8202
START = datetime(2014, 8, 3, 3, 18, 48)
NEVER_SENT = {0xAA, 0xAE}  # the PO-400's FLASH_CLEAR, protocol B's erase


def capture_replies() -> dict:
    """Opcode -> reply bytes from the capture's one-command exchanges (the last one wins)."""
    with open(FIXTURE, encoding="utf-8") as handle:
        exchanges = json.load(handle)["exchanges"]
    replies = {}
    for exchange in exchanges:
        if len(exchange["out"]) == 1:
            replies[bytes.fromhex(exchange["out"][0])[2]] = bytes.fromhex(exchange["in"])
    return replies


def model_reply(model: str) -> bytes:
    """Two `0x02` frames, as the capture's CMS50F sends them, every byte with bit 7 set."""
    name = model.encode("ascii").ljust(12, b" ")
    return (bytes([0x02, 0x80, 0x80]) + bytes(byte | 0x80 for byte in name[:6])
            + bytes([0x02, 0x80, 0x81]) + bytes(byte | 0x80 for byte in name[6:12]))


class Po250Port:
    """A serial port that answers protocol B with the capture's replies.

    `model` is the `A8` answer (None: no answer). It never answers the PO-x00 probe, as a
    protocol-B device would not. Replies come out `chunk` bytes per read.
    """

    REPLIES = capture_replies()

    def __init__(self, model=None, chunk: int = 250):
        self.model = model
        self.chunk = chunk
        self.written = []
        self.closed = False
        self._output = b""
        self._partial = b""

    def opcodes(self):
        return [data[2] for data in self.written if len(data) == 9 and data[:2] == b"\x7d\x81"]

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        self._partial += bytes(data)
        while True:
            start = self._partial.find(b"\x7d\x81")
            if start < 0 or len(self._partial) - start < 9:
                break
            command, self._partial = self._partial[start:start + 9], self._partial[start + 9:]
            opcode = command[2]
            if opcode == protocol_b.MODEL:
                if self.model is not None:
                    self._output += model_reply(self.model)
            elif opcode == protocol_b.SESSION_DATA and command[4] != 0x80:
                pass  # only recording #1 exists
            else:
                self._output += self.REPLIES.get(opcode, b"")
        if len(self._partial) > 64:
            self._partial = self._partial[-8:]
        return len(data)

    def read(self, size: int) -> bytes:
        k = min(size, self.chunk)
        output, self._output = self._output[:k], self._output[k:]
        return output

    def close(self) -> None:
        self.closed = True


class Po250Case(unittest.TestCase):
    model = None

    def setUp(self):
        self.port = Po250Port(self.model)
        self.clock = VirtualClock()
        for patcher in (
            mock.patch.object(serial_port, "open_port", lambda path: self.port),
            mock.patch.object(serial_port, "find_serial_candidates", lambda: [("/dev/ttyUSB0", "10C4", "EA60")]),
            mock.patch.object(serial_port, "time", self.clock),
            mock.patch("fiedle400.engine.cms50f37.time", self.clock),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.assertFalse(NEVER_SENT & set(self.port.opcodes()), self.port.opcodes())

    def connect(self):
        device = PulsoxHidDevice(device_path="/dev/ttyUSB0")
        with contextlib.redirect_stdout(io.StringIO()):
            device.connect()
        self.addCleanup(device.close)
        return device


class TestDecoders(unittest.TestCase):
    def test_the_capture_replies_decode(self):
        replies = capture_replies()

        def frames(opcode):
            return protocol_b.split_frames(replies[opcode], strict=True)[0]

        self.assertEqual(protocol_b.session_count(frames(protocol_b.SESSION_COUNT)), (0, 1))
        self.assertEqual(protocol_b.session_length(frames(protocol_b.SESSION_LENGTH)), 2 * ANNOUNCED)
        self.assertEqual(protocol_b.session_start(frames(protocol_b.SESSION_TIME)).as_datetime(), START)
        data = frames(protocol_b.SESSION_DATA)
        self.assertEqual(sum(len(protocol_b.samples(frame)) for frame in data), RECEIVED)

    def test_the_capture_model_reply_names_a_cms50f(self):
        with open(FIXTURE, encoding="utf-8") as handle:
            first = json.load(handle)["exchanges"][0]
        frames = protocol_b.split_frames(bytes.fromhex(first["in"]), strict=True)[0]
        self.assertEqual(protocol_b.model_from_frames(frames), "CMS50F")
        self.assertTrue(protocol_b.is_refused_model("CMS50F"))

    def test_the_gate(self):
        for refused in ("CMS50F", "CMS50I", "cms50h", "CMS50D+"):
            self.assertTrue(protocol_b.is_refused_model(refused), refused)
        for po250 in (None, "", "PO-250", "SpO2"):
            self.assertFalse(protocol_b.is_refused_model(po250), po250)

    def test_strict_framing_drops_bytes_without_bit_7(self):
        self.assertEqual(protocol_b.split_frames(b"\x0c\x00", strict=True)[0], [])
        self.assertEqual([frame.code for frame in protocol_b.split_frames(b"\x0c\x80", strict=True)[0]], [0x0C])

    def test_invalid_samples_have_no_reading(self):
        frame = protocol_b.Frame(protocol_b.REPLY_DATA, bytes([97, 60, 0, 0, 127, 255]))
        self.assertEqual(protocol_b.samples(frame), [(97, 60), (None, None), (None, None)])


class TestProbeGate(Po250Case):
    def test_a_protocol_b_device_without_a_model_string_is_a_po250(self):
        device = self.connect()
        self.assertEqual(device.protocol, "cms50f37")
        self.assertIsNone(device.model_string)
        self.assertIsInstance(serial_engine.make_engine(device), Cms50F37Engine)
        # The PO-x00 probe went first, then the protocol-B discovery: hello, user count, model.
        self.assertEqual(self.port.opcodes(), [protocol_b.HELLO1, protocol_b.HELLO2,
                                               protocol_b.USER_COUNT, protocol_b.MODEL])
        self.assertEqual(self.port.written[0][:3], b"\x7d\x81\xa7")  # the PO-x00 unlock came first
        self.assertEqual(self.port.written[1], b"\x7d\x81\x81\x01")  # and its model query

    def test_a_device_that_names_itself_cms50_is_refused(self):
        self.port.model = "CMS50F"
        with self.assertRaises(RuntimeError) as context:
            self.connect()
        self.assertIn("CMS50F", str(context.exception))
        self.assertIn("only for the PO-250", str(context.exception))

    def test_the_autoscan_refuses_a_cms50_too(self):
        self.port.model = "CMS50I"
        device = PulsoxHidDevice(backend="serial")
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(RuntimeError):
            device.connect()
        self.assertIn("found a CMS50I (protocol B, not supported), skipped", output.getvalue())

    def test_noise_without_the_protocol_b_hello_is_not_an_oximeter(self):
        class Noise(Po250Port):
            def write(self, data):
                self.written.append(bytes(data))
                self._output += b"\x0c\x00\x10\x00\x01" * 4
                return len(data)
        self.port = Noise()
        device = PulsoxHidDevice(backend="serial")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as context:
            device.connect()
        self.assertIn("No oximeter answered", str(context.exception))


class TestReplay(Po250Case):
    model = "PO-250"

    def test_sessions(self):
        engine = serial_engine.make_engine(self.connect())
        sessions = engine.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual((sessions[0].session_id, sessions[0].record_count, sessions[0].timestamp),
                         (1, ANNOUNCED, START))
        self.assertEqual(sessions[0].duration_text, "5h 48m 24s")

    def test_download_gets_what_the_capture_holds_and_warns_about_the_rest(self):
        engine = serial_engine.make_engine(self.connect())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            records = engine.download_all_sessions()
        self.assertEqual(len(records), RECEIVED)
        self.assertEqual(records[0]["timestamp"], START.isoformat())
        self.assertEqual(records[-1]["sequence"], RECEIVED - 1)
        self.assertEqual(len(engine.download_warnings), 1)
        self.assertIn(f"{RECEIVED:,} of the {ANNOUNCED:,}", output.getvalue())
        self.assertEqual(self.port.opcodes()[-1], protocol_b.HELLO1)  # stops the stream at the end

    def test_a_timeout_cap_stops_early(self):
        engine = serial_engine.make_engine(self.connect())
        with contextlib.redirect_stdout(io.StringIO()):
            records = engine.download_all_sessions(timeout_override=60)
        self.assertEqual(len(records), 60)
        self.assertEqual(engine.download_warnings, [])

    def test_erase_and_clock_are_refused_and_send_nothing(self):
        engine = serial_engine.make_engine(self.connect())
        before = list(self.port.written)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(engine.clear_memory())
            self.assertFalse(engine.clear_memory(session_id=1))
            self.assertFalse(engine.set_rtc_time(datetime.now()))
        self.assertIsNone(engine.read_rtc_time())
        self.assertEqual(self.port.written, before)


def run_cli(argv):
    output, error_output = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ), contextlib.redirect_stdout(output), \
            contextlib.redirect_stderr(error_output), mock.patch("builtins.input", return_value="n"):
        scrub_environment()
        try:
            cli.main(argv)
            exit_code = 0
        except SystemExit as error:
            exit_code = error.code or 0
    return exit_code, output.getvalue() + error_output.getvalue()


class TestCli(Po250Case):
    def test_info_names_the_po250_as_untested(self):
        exit_code, output = run_cli(["info", "-d", "/dev/ttyUSB0"])
        self.assertEqual(exit_code, 0, output)
        self.assertIn("Pulox PO-250 (protocol B, model not reported)", output)
        self.assertIn("has not been tested", output)

    def test_sessions(self):
        exit_code, output = run_cli(["sessions", "-d", "/dev/ttyUSB0"])
        self.assertEqual(exit_code, 0, output)
        self.assertIn("2014-08-03", output)

    def test_download_to_csv_matches_the_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "po250.csv")
            exit_code, output = run_cli(["download", "-d", "/dev/ttyUSB0", "-f", "csv", "-o", path])
            self.assertEqual(exit_code, 0, output)
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), RECEIVED)
        self.assertIn("warning", output.lower())

    def test_clear_and_set_time_are_refused(self):
        exit_code, output = run_cli(["clear", "-d", "/dev/ttyUSB0", "--yes"])
        self.assertEqual(exit_code, 1, output)
        exit_code, output = run_cli(["set-time", "-d", "/dev/ttyUSB0"])
        self.assertEqual(exit_code, 1, output)
        self.assertIn("not supported for the PO-250", output)

    def test_live_mode_is_refused(self):
        exit_code, output = run_cli(["detect", "-d", "/dev/ttyUSB0"])
        self.assertEqual(exit_code, 1, output)
        self.assertIn("Live mode is not supported for the PO-250", output)


if __name__ == "__main__":
    unittest.main()
