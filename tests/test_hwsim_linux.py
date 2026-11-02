"""Mock-hardware tests: the real Linux hidraw code path against a simulated PO-400.

The simulator (tests/hwsim.py) replays device bytes recorded in
analysis/bum400_20260906_100516.pcap. The hidraw backend, the sysfs scan, the engine,
the detector and the CLI are the real code; only the kernel node and the device
behind it are simulated. See tests/hwsim.py for what that does and does not cover.

Tests marked ``expectedFailure`` pin known defects found while building the
simulator (RELEASE_PLAN.md section 3d); none are open at the moment. T1 to T7 were pinned this way
and are fixed: their tests now assert the correct behaviour.
"""

import contextlib
import csv
import errno
import io
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import scrub_environment, FakeOximeter, HidrawSim, Trace, VirtualClock, command_key  # noqa: E402

from fiedle400 import cli, export, hid_driver  # noqa: E402
from fiedle400.engine import SerialDeviceEngine, SerialPacketDetector, SerialByteStreamBuffer  # noqa: E402
from fiedle400.hid_driver import LinuxHidrawBackend, PulsoxHidDevice, find_pulsox_hid_devices  # noqa: E402
from fiedle400.protocol import Commands  # noqa: E402
from fiedle400.protocol.decompression import decode_ed_subframes  # noqa: E402

LINUX = sys.platform.startswith("linux")
PCAP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analysis", "bum400_20260906_100516.pcap"))

# Outbound commands as written in PROTOCOL.md (prefixes: the CLI pads with 0x80 or 0x00 after these).
UNLOCK = "7d81a7808080808080" + "7d81a2"
RESET_INDEX = "7d819c8000"
QUERY_SESSIONS = "7d819c011d"
STORAGE_INIT = "9d027f7f7f0000001c"
SPO2_PAGE0 = "9d0401010100000024"
PULSE_PAGE0 = "9d0402010100000025"
SPO2_PAGE1 = "9d0401010101000025"
PULSE_PAGE1 = "9d0402010101000026"
SEGMENT_ACK = "9d027f7f7f0000001c"

_TRACE = None


def trace() -> Trace:
    global _TRACE
    if _TRACE is None:
        _TRACE = Trace.from_pcap(PCAP)
    return _TRACE


def fresh_fake(**kwargs) -> FakeOximeter:
    return FakeOximeter(trace(), **kwargs)


def collapse(hexes):
    """Drop consecutive repeats (retries) from a list of command hex strings."""
    output = []
    for hex_text in hexes:
        if not output or output[-1] != hex_text:
            output.append(hex_text)
    return output


def match_prefix(report: bytes, prefixes):
    for prefix in prefixes:
        if report.hex().startswith(prefix):
            return prefix
    return report[:10].hex()


KNOWN = [UNLOCK, RESET_INDEX, QUERY_SESSIONS, STORAGE_INIT, SPO2_PAGE0, PULSE_PAGE0,
         SPO2_PAGE1, PULSE_PAGE1, SEGMENT_ACK]


def sent_names(fake):
    return collapse([match_prefix(report, KNOWN) for report in fake.sent])


def run_cli(argv):
    """Run cli.main, returning (exit code, stdout, stderr)."""
    output, error_output = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
        scrub_environment()
        try:
            exit_code = cli.main(argv)
        except SystemExit as event:
            exit_code = event.code
    return exit_code, output.getvalue(), error_output.getvalue()


# --------------------------------------------------------------------------
# Platform-neutral: command matching and the fake itself
# --------------------------------------------------------------------------
class TestCommandKey(unittest.TestCase):
    def test_framing_padding_and_dialect_do_not_change_the_key(self):
        vendor = bytes.fromhex("9c011d") + bytes(61)
        cli_form = Commands.query_sessions()
        self.assertEqual(command_key(vendor), command_key(cli_form))
        self.assertEqual(command_key(bytes.fromhex("9d027f7f7f00001c")),   # vendor tool: 8 bytes
                         command_key(Commands.storage_init()))             # CLI: 9 bytes

    def test_block_reads_are_distinguished_by_type_and_page(self):
        keys = {command_key(Commands.session_page(data_type, 1, page)) for data_type in (1, 2) for page in (0, 1)}
        self.assertEqual(len(keys), 4)

    def test_destructive_opcodes_are_recognised(self):
        for opcode in (0xAA, 0xAB, 0xAC, 0x91, 0x92, 0x93, 0x95, 0x96):
            self.assertEqual(command_key(Commands.build_hid(opcode, [0x80, 0x80])), ("destructive", opcode), hex(opcode))
        self.assertEqual(command_key(bytes.fromhex("9406")), ("destructive", 0x94))

    def test_read_only_queries_are_not_destructive(self):
        for report in (Commands.read_time(), Commands.query_sessions(), Commands.reset_session_index(),
                    Commands.segment_ack(), bytes.fromhex("9414")):
            key = command_key(report)
            self.assertIsNotNone(key)
            self.assertNotEqual(key[0], "destructive")

    def test_unknown_opcode_has_no_key(self):
        self.assertIsNone(command_key(bytes([0xC3]) + bytes(63)))


class TestFakeOximeter(unittest.TestCase):
    def test_replays_recorded_device_bytes(self):
        fake = fresh_fake()
        fake.handle_output(Commands.unlock_handshake())
        self.assertEqual(fake.poll()[:2], bytes([0xF0, 0x70]))
        fake.handle_output(Commands.query_sessions())
        header = fake.poll()
        self.assertEqual(header[:2], bytes([0xEC, 0x40]))
        self.assertEqual(header[4:10], bytes([26, 9, 6, 10, 0, 46]))  # 2026-09-06 10:00:46

    def test_unknown_commands_are_logged_and_never_answered(self):
        fake = fresh_fake()
        fake.handle_output(Commands.build_hid(0xAD))
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.unmatched), 1)

    def test_destructive_commands_are_recorded_and_refused(self):
        trace = Trace()
        trace.add(Commands.build_hid(0xAA, [0x80, 0x80]), [bytes([0xF0, 0x70]) + bytes(62)])  # even if "recorded"
        fake = FakeOximeter(trace)
        fake.handle_output(Commands.build_hid(0xAA, [0x80, 0x80]))
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.destructive), 1)

    def test_strict_fake_does_not_repeat_the_last_recording(self):
        trace = Trace()
        query = Commands.query_sessions()
        trace.add(query, [b"\xec" + bytes([1]) + bytes(62)])
        fake = FakeOximeter(trace, strict=True)
        fake.handle_output(query)
        self.assertEqual(fake.poll()[1], 1)
        fake.handle_output(query)
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.unmatched), 1)

    def test_nth_repeat_gets_nth_recording_and_the_last_repeats(self):
        trace = Trace()
        query = Commands.query_sessions()
        trace.add(query, [b"\xec" + bytes([1]) + bytes(62)])
        trace.add(query, [b"\xec" + bytes([2]) + bytes(62)])
        fake = FakeOximeter(trace)
        got = []
        for _ in range(3):
            fake.handle_output(query)
            got.append(fake.poll()[1])
        self.assertEqual(got, [1, 2, 2])

    def test_fault_hook_can_drop_and_replace_reports(self):
        fake = fresh_fake(fault=lambda key, i, report: None if i == 0 else report)
        fake.handle_output(Commands.build_hid(0x82))   # read time: one report, dropped
        self.assertIsNone(fake.poll())

    def test_sent_log_keeps_every_report_unmodified(self):
        fake = fresh_fake()
        commands = [Commands.unlock_handshake(), Commands.read_time(), Commands.build_hid(0xAD)]
        for command in commands:
            fake.handle_output(command)
        self.assertEqual(fake.sent, commands)


class TestPcapTrace(unittest.TestCase):
    def test_capture_covers_what_the_docs_say_it_covers(self):
        keys = trace().keys()
        self.assertIn(("unlock",), keys)
        self.assertIn((0x9C, 0x01), keys)
        self.assertIn((0x9D, 0x04, 1, 1, 1, 0, 0), keys)   # SpO2 page 0
        self.assertIn((0x9D, 0x04, 2, 1, 1, 0, 0), keys)   # pulse page 0
        self.assertNotIn((0x9D, 0x04, 1, 1, 1, 1, 0), keys)  # page 1 was never requested

    def test_every_recorded_storage_frame_has_a_valid_checksum(self):
        """Real firmware always sends a correct 7-bit checksum; the corruption tests rely on it."""
        for key in ((0x9D, 0x04, 1, 1, 1, 0, 0), (0x9D, 0x04, 2, 1, 1, 0, 0)):
            stream = b"".join(trace().responses(key)[0])
            frames = [stream[i:i + 30] for i in range(0, len(stream) - 29, 30) if stream[i] == 0xED]
            self.assertEqual(len(frames), 6)
            for frame in frames:
                self.assertEqual(sum(frame[:29]) & 0x7F, frame[29])

    def test_json_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "t.json")
            trace().to_json(path)
            again = Trace.from_json(path)
        self.assertEqual(again.keys(), trace().keys())
        self.assertEqual([group[2] for group in again.groups], [recorded_group[2] for recorded_group in trace().groups])


# --------------------------------------------------------------------------
# Linux: the real hidraw backend against the simulated node
# --------------------------------------------------------------------------
@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestHidrawDiscovery(unittest.TestCase):
    def test_sysfs_scan_finds_the_simulated_node(self):
        with HidrawSim(fresh_fake()):
            devices = find_pulsox_hid_devices()
        self.assertEqual(len(devices), 1)
        path, uevent, readable = devices[0]
        self.assertTrue(path.endswith("hidraw7"))
        self.assertIn("28E9", uevent.upper())
        self.assertTrue(readable)

    def test_no_device_found_when_nothing_is_plugged_in(self):
        with HidrawSim(fresh_fake(), present=False):
            self.assertEqual(find_pulsox_hid_devices(), [])
            with self.assertRaises(RuntimeError) as caught:
                PulsoxHidDevice(backend="hidraw").connect()
        self.assertIn("No Pulsox PO-400 device found", str(caught.exception))

    def test_other_hid_devices_are_ignored(self):
        with HidrawSim(fresh_fake()) as simulator:
            other = os.path.join(simulator.sysfs_root, "hidraw3", "device")
            os.makedirs(other)
            with open(os.path.join(other, "uevent"), "w") as file:
                file.write("HID_ID=0003:0000046D:0000C52B\nHID_NAME=Some Mouse\n")
            devices = find_pulsox_hid_devices()
        self.assertEqual([os.path.basename(device[0]) for device in devices], ["hidraw7"])

    def test_unreadable_node_gives_a_permission_hint(self):
        with HidrawSim(fresh_fake()):
            with mock.patch.object(hid_driver.os, "access", return_value=False):
                with self.assertRaises(PermissionError) as caught:
                    PulsoxHidDevice(backend="hidraw").connect()
        self.assertIn("udev", str(caught.exception))

    def test_connect_opens_the_node_read_write_and_non_blocking(self):
        with HidrawSim(fresh_fake()) as simulator:
            device = PulsoxHidDevice(backend="hidraw")
            path = device.connect()
            self.assertEqual(path, simulator.device_path)
            self.assertEqual(len(simulator.open_flags), 1)
            flags = simulator.open_flags[0]
            self.assertTrue(flags & os.O_RDWR)
            self.assertTrue(flags & os.O_NONBLOCK, "a blocking read would hang the engine's polling loops")
            meta = device.get_descriptor_info()
            device.close()
        self.assertEqual((meta["vid_hex"], meta["pid_hex"]), ("28E9", "028A"))
        self.assertIn("Contec", meta["manufacturer"])
        self.assertEqual(meta["product"], "Pulse Oximeter")


@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestHidrawBackendIO(unittest.TestCase):
    def setUp(self):
        self.fake = fresh_fake()
        self.simulator = HidrawSim(self.fake)
        self.simulator.__enter__()
        self.addCleanup(self.simulator.__exit__, None, None, None)
        self.backend = LinuxHidrawBackend()
        self.backend.connect()
        self.addCleanup(self.backend.close)

    def test_empty_read_returns_none_instead_of_blocking(self):
        self.assertIsNone(self.backend.read_report(64))

    def test_reports_arrive_whole_and_in_order(self):
        self.backend.write_report(Commands.unlock_handshake())
        self.backend.write_report(Commands.read_time())
        first, second = self.backend.read_report(64), self.backend.read_report(64)
        self.assertEqual((len(first), len(second)), (64, 64))
        self.assertEqual(first[:2], bytes([0xF0, 0x70]))
        self.assertEqual(second[0], 0xF2)
        self.assertIsNone(self.backend.read_report(64))

    def test_write_reports_exactly_the_bytes_the_host_sent(self):
        command = Commands.session_page(1, 1, 0)
        self.assertEqual(self.backend.write_report(command), 64)
        self.assertEqual(self.fake.sent, [command])

    def test_unplug_surfaces_as_enodev_not_as_an_empty_read(self):
        self.simulator.unplug()
        with self.assertRaises(OSError) as caught:
            self.backend.read_report(64)
        self.assertEqual(caught.exception.errno, errno.ENODEV)
        with self.assertRaises(OSError) as caught:
            self.backend.write_report(Commands.read_time())
        self.assertEqual(caught.exception.errno, errno.ENODEV)

    def test_closed_backend_refuses_io(self):
        self.backend.close()
        self.assertFalse(self.backend.is_connected())
        with self.assertRaises(RuntimeError):
            self.backend.read_report(64)


# --------------------------------------------------------------------------
# Linux: whole flows through backend, engine, detector, export and CLI
# --------------------------------------------------------------------------
@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class FlowCase(unittest.TestCase):
    def make_fake(self) -> FakeOximeter:
        return fresh_fake()

    def setUp(self):
        self.fake = self.make_fake()
        self.clock = VirtualClock()
        self.simulator = HidrawSim(self.fake)
        self.simulator.__enter__()
        self.addCleanup(self.simulator.__exit__, None, None, None)
        clock_patch = self.clock.patch()
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.device = PulsoxHidDevice(backend="hidraw")
        self.device.connect()
        self.addCleanup(self.device.close)
        self.engine = SerialDeviceEngine(self.device)

    def unmatched_keys(self):
        return {command_key(report) for report in self.fake.unmatched}

    def download(self):
        session = self.engine.list_sessions()[0]
        with contextlib.redirect_stdout(io.StringIO()):
            return self.engine.download_session(session)


class TestSessionsFlow(FlowCase):
    def test_lists_the_recorded_session(self):
        sessions = self.engine.list_sessions()
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        self.assertEqual((session.session_id, session.user_id, session.record_count, session.raw_samples), (1, 1, 243, 243))
        self.assertEqual(session.timestamp.isoformat(), "2026-09-06T10:00:46")

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual(sent_names(self.fake), [UNLOCK, RESET_INDEX, QUERY_SESSIONS])

    def test_only_the_reset_is_unanswered(self):
        self.engine.list_sessions()
        self.assertEqual(self.unmatched_keys(), {(0x9C, 0x80)})

    def test_header_count_is_seconds_so_duration_is_four_minutes(self):
        """T-075 (reverses T3): the header says 243 samples, one per second = 4m 03s. The next
        recording in every capture starts 13-18 s after start + count seconds."""
        session = self.engine.list_sessions()[0]
        self.assertEqual(session.duration_seconds, 243)
        self.assertEqual(session.duration_text, "4m 03s")


class TestDownloadFlow(FlowCase):
    def test_command_sequence_matches_the_documented_download(self):
        self.download()
        self.assertEqual(
            sent_names(self.fake),
            [UNLOCK, RESET_INDEX, QUERY_SESSIONS,                 # list
             UNLOCK, STORAGE_INIT, SPO2_PAGE0, PULSE_PAGE0,        # page 0 of both series
                                                                   # 243 records are reached: no further page
             SEGMENT_ACK],
        )

    def test_page_requests_are_the_exact_documented_bytes(self):
        self.download()
        by_prefix = {page_prefix: [report for report in self.fake.sent if report.hex().startswith(page_prefix)] for page_prefix in (SPO2_PAGE0, PULSE_PAGE0)}
        for prefix, found in by_prefix.items():
            self.assertEqual(len(found), 1, prefix)
            self.assertEqual(len(found[0]), 64)

    def test_unanswered_page_is_retried_then_abandoned_cleanly(self):
        """A session announcing more samples than the recording holds makes the engine ask for the next
        window (offset 243 = after 243 records), which the recording does not contain."""
        self.fake.trace = trace().with_header_samples(400)
        records = self.download()
        retries = [report for report in self.fake.sent if report.hex().startswith(Commands.session_page(1, 1, 243, 1)[:9].hex())]
        self.assertEqual(len(retries), 3, "one request plus two retries")
        self.assertTrue(records)

    def test_never_sends_a_destructive_command(self):
        self.engine.read_device_info()
        self.download()
        self.assertEqual(self.fake.destructive, [])
        self.assertFalse({0xAA, 0xAB, 0xAC, 0x91, 0x92, 0x93, 0x95, 0x96} & set(self.fake.opcodes_sent()))

    def test_ends_with_the_non_destructive_segment_ack(self):
        self.download()
        self.assertTrue(self.fake.sent[-1].hex().startswith(SEGMENT_ACK))

    def test_decoded_values_match_an_independent_decompression_of_the_same_frames(self):
        records = self.download()
        series = {}
        for data_type in (1, 2):
            stream = b"".join(trace().responses((0x9D, 0x04, data_type, 1, 1, 0, 0))[0])
            frames = [stream[i:i + 30] for i in range(0, len(stream) - 29, 30)]
            series[data_type] = decode_ed_subframes(frames, is_spo2=(data_type == 1))
        self.assertEqual(len(series[1]), 243)   # one value per second, as the header says
        self.assertEqual([record["spo2"] for record in records], series[1])
        self.assertEqual([record["heart_rate"] for record in records], series[2])

    def test_timestamps_follow_the_session_start_at_one_per_second(self):
        records = self.download()
        self.assertEqual(records[0]["timestamp"], "2026-09-06T10:00:46")
        self.assertEqual(records[-1]["timestamp"], "2026-09-06T10:04:48")

    def test_good_samples_are_not_blanked_at_page_end(self):
        """T1 (fixed): the last frame of a page has a non-zero MSB mask in byte 7, which the detector used
        to read as status flags ("searching,low-perfusion"), so the engine stored those samples as None."""
        records = self.download()
        self.assertEqual([record for record in records if record["spo2"] is None], [])

    def test_export_writes_every_record(self):
        records = self.download()
        with tempfile.TemporaryDirectory() as directory:
            csv_path = export.export_records(records, output_filename=os.path.join(directory, "r.csv"))
            with open(csv_path, newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file))), 243)
            spo2_path = export.export_records(records, output_filename=os.path.join(directory, "r.spo2"))
            with open(spo2_path, "rb") as file:
                blob = file.read()
        self.assertEqual(struct.unpack_from("<I", blob, 0x0438)[0], 243)
        self.assertEqual(len(blob), export.SPO2_HEADER_SIZE + 243 * 2)


class TestInfoFlow(FlowCase):
    def test_reads_clock_and_user_from_recorded_replies(self):
        result = self.engine.read_device_info()
        self.assertEqual(result["rtc_time_text"], "not reported by the device")
        self.assertEqual(result["device_info"].user_profile, "user")

    def test_unrecorded_queries_are_the_only_unanswered_ones(self):
        self.engine.read_device_info()
        self.assertEqual(self.unmatched_keys(), {(0xAD,), (0x9E, 0x40, 0x04)})


@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestFaults(unittest.TestCase):
    """What the CLI does when the device misbehaves."""

    def run_download(self, fault=None, unplug_after=None, extra=()):
        fake = fresh_fake(fault=fault)
        with tempfile.TemporaryDirectory() as directory, HidrawSim(fake) as simulator, VirtualClock().patch():
            if unplug_after is not None:
                orig = fake.handle_output

                def hooked(report):
                    orig(report)
                    if len(fake.sent) == unplug_after:
                        simulator.unplug()
                fake.handle_output = hooked
            output_path = os.path.join(directory, "out.csv")
            exit_code, output, error_output = run_cli(["download", "--backend", "hidraw", "-o", output_path, *extra])
            written = os.path.exists(output_path)
            rows = None
            if written:
                with open(output_path, newline="") as file:
                    rows = len(list(csv.DictReader(file)))
        return exit_code, output, error_output, written, rows, fake

    def test_normal_download_through_the_cli(self):
        exit_code, output, error_output, written, rows, fake = self.run_download()
        self.assertEqual(exit_code, 0)
        self.assertTrue(written)
        self.assertEqual(rows, 243)

    def test_timeout_flag_caps_the_download(self):
        """-t/--timeout used to be ignored for real sessions (record_count won over duration)."""
        exit_code, output, error_output, written, rows, fake = self.run_download(extra=("-t", "30"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(rows, 30)

    def test_unplugged_mid_download_fails_with_one_clear_line_and_writes_nothing(self):
        exit_code, output, error_output, written, rows, fake = self.run_download(unplug_after=7)
        self.assertEqual(exit_code, 1)
        self.assertFalse(written)
        self.assertIn("No such device", output + error_output)
        self.assertNotIn("Traceback", output + error_output)

    def test_unplugged_before_connecting_reports_no_device(self):
        fake = fresh_fake()
        with HidrawSim(fake, present=False), tempfile.TemporaryDirectory() as directory:
            exit_code, output, error_output = run_cli(["download", "--backend", "hidraw", "-o", os.path.join(directory, "o.csv")])
        self.assertEqual(exit_code, 1)
        self.assertIn("No Pulsox PO-400 device found", output + error_output)

    def test_dropped_page_frame_gives_fewer_records_without_crashing(self):
        def drop_last_report_of_pages(key, i, report):
            return None if (key[:2] == (0x9D, 0x04) and i == 2) else report
        exit_code, output, error_output, written, rows, fake = self.run_download(fault=drop_last_report_of_pages)
        self.assertEqual(exit_code, 0)
        self.assertLess(rows, 243)

    def test_device_that_never_answers_is_not_reported_as_a_successful_download(self):
        """T2 (fixed): with every reply dropped, `download` used to invent "Session #1 / 60 records",
        find nothing, save an empty file and exit 0. A dead or ignoring device is an error."""
        exit_code, output, error_output, written, rows, fake = self.run_download(fault=lambda key, i, report: None)
        self.assertEqual(exit_code, 1)
        self.assertFalse(written)
        self.assertIn("No recording data was received", output + error_output)

    def test_info_does_not_print_made_up_values_when_the_device_is_silent(self):
        """T4 (fixed): `info` used to fall back to hard-coded firmware "v2.0", serial "50F", user and
        geometry when the device did not answer, so they looked like device readings."""
        fake = fresh_fake(fault=lambda key, i, report: None)
        with HidrawSim(fake), VirtualClock().patch():
            exit_code, output, error_output = run_cli(["info", "--backend", "hidraw"])
        self.assertNotIn("v2.0", output)
        self.assertNotIn("50F", output)
        self.assertNotIn("Sub-chunk", output)
        for label in ("Firmware Version", "Serial Number", "User Profile String", "Storage Memory Geometry"):
            self.assertRegex(output, rf"{label}\s*: not reported by the device")

    def test_frame_with_a_bad_checksum_is_rejected(self):
        """T5 (fixed): the detector never verified the 7-bit checksum that every real frame carries."""
        stream = b"".join(trace().responses((0x9D, 0x04, 1, 1, 1, 0, 0))[0])
        frame = bytearray(stream[30:60])
        frame[10] ^= 0x01                       # flip a data bit, leave the checksum stale
        self.assertNotEqual(sum(frame[:29]) & 0x7F, frame[29])
        buffer = SerialByteStreamBuffer()
        buffer.write(bytes(frame))
        events = SerialPacketDetector.detect_and_decode_stream(buffer)
        self.assertEqual([event for event in events if event.packet_type == "STORED_BLOCK"], [])
        self.assertEqual([event.packet_type for event in events], ["CORRUPT_FRAME"])

    def test_download_with_a_corrupted_frame_warns_and_still_finishes(self):
        def corrupt(key, i, report):
            if key[:2] == (0x9D, 0x04) and key[2] == 1 and i == 0:
                data = bytearray(report)
                data[40] ^= 0x01                   # inside the second frame's data
                return bytes(data)
            return report
        exit_code, output, error_output, written, rows, fake = self.run_download(fault=corrupt)
        self.assertEqual(exit_code, 0)
        self.assertIn("1 stored frame(s) failed their checksum", output)
        self.assertIn("Download it again", output)


# --------------------------------------------------------------------------
# The recorder tool, against the simulator
# --------------------------------------------------------------------------
@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestRecorder(unittest.TestCase):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))

    def test_recorded_traffic_replays_to_the_same_result(self):
        import record_exchange
        fake = fresh_fake()
        with HidrawSim(fake), VirtualClock().patch(), contextlib.redirect_stdout(io.StringIO()):
            device = PulsoxHidDevice(backend="hidraw")
            device.connect()
            recorded = record_exchange.record(device, download=True)
            device.close()
        self.assertEqual(fake.destructive, [])
        self.assertGreater(len(recorded.groups), 5)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "rec.trace.json")
            recorded.to_json(path)
            replay = Trace.from_json(path)

        fake2 = FakeOximeter(replay)
        with HidrawSim(fake2), VirtualClock().patch(), contextlib.redirect_stdout(io.StringIO()):
            device = PulsoxHidDevice(backend="hidraw")
            device.connect()
            engine = SerialDeviceEngine(device)
            again = engine.download_session(engine.list_sessions()[0])
            device.close()
        self.assertEqual(len(again), 243)

    def test_recorder_refuses_destructive_commands(self):
        import record_exchange
        fake = fresh_fake()
        with HidrawSim(fake):
            device = PulsoxHidDevice(backend="hidraw")
            device.connect()
            record = record_exchange.RecordingDevice(device)
            with self.assertRaises(record_exchange.RefusedCommand):
                record.write_report(Commands.build_hid(0xAA, [0x80, 0x80]))
            device.close()
        self.assertEqual(fake.sent, [], "a refused command must never reach the device")


if __name__ == "__main__":
    unittest.main()
