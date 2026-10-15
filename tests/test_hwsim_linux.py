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
import hwsim  # noqa: E402
from hwsim import FakeOximeter, HidrawSim, Trace, VirtualClock, command_key  # noqa: E402

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


def fresh_fake(**kw) -> FakeOximeter:
    return FakeOximeter(trace(), **kw)


def collapse(hexes):
    """Drop consecutive repeats (retries) from a list of command hex strings."""
    out = []
    for h in hexes:
        if not out or out[-1] != h:
            out.append(h)
    return out


def match_prefix(report: bytes, prefixes):
    for p in prefixes:
        if report.hex().startswith(p):
            return p
    return report[:10].hex()


KNOWN = [UNLOCK, RESET_INDEX, QUERY_SESSIONS, STORAGE_INIT, SPO2_PAGE0, PULSE_PAGE0,
         SPO2_PAGE1, PULSE_PAGE1, SEGMENT_ACK]


def sent_names(fake):
    return collapse([match_prefix(r, KNOWN) for r in fake.sent])


def run_cli(argv):
    """Run cli.main, returning (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cli.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


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
        keys = {command_key(Commands.session_page(t, 1, p)) for t in (1, 2) for p in (0, 1)}
        self.assertEqual(len(keys), 4)

    def test_destructive_opcodes_are_recognised(self):
        for op in (0xAA, 0xAB, 0xAC, 0x91, 0x92, 0x93, 0x95, 0x96):
            self.assertEqual(command_key(Commands.build_hid(op, [0x80, 0x80])), ("destructive", op), hex(op))
        self.assertEqual(command_key(bytes.fromhex("9406")), ("destructive", 0x94))

    def test_read_only_queries_are_not_destructive(self):
        for rep in (Commands.read_time(), Commands.query_sessions(), Commands.reset_session_index(),
                    Commands.segment_ack(), bytes.fromhex("9414")):
            key = command_key(rep)
            self.assertIsNotNone(key)
            self.assertNotEqual(key[0], "destructive")

    def test_unknown_opcode_has_no_key(self):
        self.assertIsNone(command_key(bytes([0xC3]) + bytes(63)))


class TestFakeOximeter(unittest.TestCase):
    def test_replays_recorded_device_bytes(self):
        fake = fresh_fake()
        fake.handle_out(Commands.unlock_handshake())
        self.assertEqual(fake.poll()[:2], bytes([0xF0, 0x70]))
        fake.handle_out(Commands.query_sessions())
        hdr = fake.poll()
        self.assertEqual(hdr[:2], bytes([0xEC, 0x40]))
        self.assertEqual(hdr[4:10], bytes([26, 9, 6, 10, 0, 46]))  # 2026-09-06 10:00:46

    def test_unknown_commands_are_logged_and_never_answered(self):
        fake = fresh_fake()
        fake.handle_out(Commands.build_hid(0xAD))
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.unmatched), 1)

    def test_destructive_commands_are_recorded_and_refused(self):
        t = Trace()
        t.add(Commands.build_hid(0xAA, [0x80, 0x80]), [bytes([0xF0, 0x70]) + bytes(62)])  # even if "recorded"
        fake = FakeOximeter(t)
        fake.handle_out(Commands.build_hid(0xAA, [0x80, 0x80]))
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.destructive), 1)

    def test_strict_fake_does_not_repeat_the_last_recording(self):
        t = Trace()
        q = Commands.query_sessions()
        t.add(q, [b"\xec" + bytes([1]) + bytes(62)])
        fake = FakeOximeter(t, strict=True)
        fake.handle_out(q)
        self.assertEqual(fake.poll()[1], 1)
        fake.handle_out(q)
        self.assertIsNone(fake.poll())
        self.assertEqual(len(fake.unmatched), 1)

    def test_nth_repeat_gets_nth_recording_and_the_last_repeats(self):
        t = Trace()
        q = Commands.query_sessions()
        t.add(q, [b"\xec" + bytes([1]) + bytes(62)])
        t.add(q, [b"\xec" + bytes([2]) + bytes(62)])
        fake = FakeOximeter(t)
        got = []
        for _ in range(3):
            fake.handle_out(q)
            got.append(fake.poll()[1])
        self.assertEqual(got, [1, 2, 2])

    def test_fault_hook_can_drop_and_replace_reports(self):
        fake = fresh_fake(fault=lambda key, i, rep: None if i == 0 else rep)
        fake.handle_out(Commands.build_hid(0x82))   # read time: one report, dropped
        self.assertIsNone(fake.poll())

    def test_sent_log_keeps_every_report_unmodified(self):
        fake = fresh_fake()
        cmds = [Commands.unlock_handshake(), Commands.read_time(), Commands.build_hid(0xAD)]
        for c in cmds:
            fake.handle_out(c)
        self.assertEqual(fake.sent, cmds)


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
            for f in frames:
                self.assertEqual(sum(f[:29]) & 0x7F, f[29])

    def test_json_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.json")
            trace().to_json(p)
            again = Trace.from_json(p)
        self.assertEqual(again.keys(), trace().keys())
        self.assertEqual([g[2] for g in again.groups], [g[2] for g in trace().groups])


# --------------------------------------------------------------------------
# Linux: the real hidraw backend against the simulated node
# --------------------------------------------------------------------------
@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestHidrawDiscovery(unittest.TestCase):
    def test_sysfs_scan_finds_the_simulated_node(self):
        with HidrawSim(fresh_fake()) as sim:
            devs = find_pulsox_hid_devices()
        self.assertEqual(len(devs), 1)
        path, uevent, readable = devs[0]
        self.assertTrue(path.endswith("hidraw7"))
        self.assertIn("28E9", uevent.upper())
        self.assertTrue(readable)

    def test_no_device_found_when_nothing_is_plugged_in(self):
        with HidrawSim(fresh_fake(), present=False):
            self.assertEqual(find_pulsox_hid_devices(), [])
            with self.assertRaises(RuntimeError) as cm:
                PulsoxHidDevice(backend="hidraw").connect()
        self.assertIn("No Pulsox PO-400 device found", str(cm.exception))

    def test_other_hid_devices_are_ignored(self):
        with HidrawSim(fresh_fake()) as sim:
            other = os.path.join(sim.sysfs_root, "hidraw3", "device")
            os.makedirs(other)
            with open(os.path.join(other, "uevent"), "w") as fh:
                fh.write("HID_ID=0003:0000046D:0000C52B\nHID_NAME=Some Mouse\n")
            devs = find_pulsox_hid_devices()
        self.assertEqual([os.path.basename(d[0]) for d in devs], ["hidraw7"])

    def test_unreadable_node_gives_a_permission_hint(self):
        with HidrawSim(fresh_fake()):
            with mock.patch.object(hid_driver.os, "access", return_value=False):
                with self.assertRaises(PermissionError) as cm:
                    PulsoxHidDevice(backend="hidraw").connect()
        self.assertIn("udev", str(cm.exception))

    def test_connect_opens_the_node_read_write_and_non_blocking(self):
        with HidrawSim(fresh_fake()) as sim:
            dev = PulsoxHidDevice(backend="hidraw")
            path = dev.connect()
            self.assertEqual(path, sim.dev_path)
            self.assertEqual(len(sim.open_flags), 1)
            flags = sim.open_flags[0]
            self.assertTrue(flags & os.O_RDWR)
            self.assertTrue(flags & os.O_NONBLOCK, "a blocking read would hang the engine's polling loops")
            meta = dev.get_descriptor_info()
            dev.close()
        self.assertEqual((meta["vid_hex"], meta["pid_hex"]), ("28E9", "028A"))
        self.assertIn("Contec", meta["manufacturer"])
        self.assertEqual(meta["product"], "Pulse Oximeter")


@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestHidrawBackendIO(unittest.TestCase):
    def setUp(self):
        self.fake = fresh_fake()
        self.sim = HidrawSim(self.fake)
        self.sim.__enter__()
        self.addCleanup(self.sim.__exit__, None, None, None)
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
        cmd = Commands.session_page(1, 1, 0)
        self.assertEqual(self.backend.write_report(cmd), 64)
        self.assertEqual(self.fake.sent, [cmd])

    def test_unplug_surfaces_as_enodev_not_as_an_empty_read(self):
        self.sim.unplug()
        with self.assertRaises(OSError) as cm:
            self.backend.read_report(64)
        self.assertEqual(cm.exception.errno, errno.ENODEV)
        with self.assertRaises(OSError) as cm:
            self.backend.write_report(Commands.read_time())
        self.assertEqual(cm.exception.errno, errno.ENODEV)

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
        self.sim = HidrawSim(self.fake)
        self.sim.__enter__()
        self.addCleanup(self.sim.__exit__, None, None, None)
        clock_patch = self.clock.patch()
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.dev = PulsoxHidDevice(backend="hidraw")
        self.dev.connect()
        self.addCleanup(self.dev.close)
        self.engine = SerialDeviceEngine(self.dev)

    def unmatched_keys(self):
        return {command_key(r) for r in self.fake.unmatched}

    def download(self):
        sess = self.engine.list_sessions()[0]
        with contextlib.redirect_stdout(io.StringIO()):
            return self.engine.download_session(sess)


class TestSessionsFlow(FlowCase):
    def test_lists_the_recorded_session(self):
        sessions = self.engine.list_sessions()
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual((s.session_id, s.user_id, s.record_count, s.raw_samples), (1, 1, 122, 243))
        self.assertEqual(s.timestamp.isoformat(), "2026-09-06T10:00:46")

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual(sent_names(self.fake), [UNLOCK, RESET_INDEX, QUERY_SESSIONS])

    def test_only_the_reset_is_unanswered(self):
        self.engine.list_sessions()
        self.assertEqual(self.unmatched_keys(), {(0x9C, 0x80)})

    def test_header_count_is_in_raw_2hz_samples_so_duration_is_about_two_minutes(self):
        """T3 (fixed): the header says 243 raw 2 Hz values = 122 s (an odd count keeps its last
        reading), where SessionInfo used to read the number as seconds and print 4m 03s."""
        s = self.engine.list_sessions()[0]
        self.assertEqual(s.duration_seconds, 122)
        self.assertEqual(s.duration_str, "2m 02s")


class TestDownloadFlow(FlowCase):
    def test_command_sequence_matches_the_documented_download(self):
        self.download()
        self.assertEqual(
            sent_names(self.fake),
            [UNLOCK, RESET_INDEX, QUERY_SESSIONS,                 # list
             UNLOCK, STORAGE_INIT, SPO2_PAGE0, PULSE_PAGE0,        # page 0 of both series
                                                                   # 122 records are reached: no further page
             SEGMENT_ACK],
        )

    def test_page_requests_are_the_exact_documented_bytes(self):
        self.download()
        by_prefix = {p: [r for r in self.fake.sent if r.hex().startswith(p)] for p in (SPO2_PAGE0, PULSE_PAGE0)}
        for prefix, found in by_prefix.items():
            self.assertEqual(len(found), 1, prefix)
            self.assertEqual(len(found[0]), 64)

    def test_unanswered_page_is_retried_then_abandoned_cleanly(self):
        """A session announcing more samples than the recording holds makes the engine ask for the next
        window (offset 244 = after 122 records), which the recording does not contain."""
        self.fake.trace = trace().with_header_samples(400)
        records = self.download()
        retries = [r for r in self.fake.sent if r.hex().startswith(Commands.session_page(1, 1, 244, 1)[:9].hex())]
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
        for dtype in (1, 2):
            stream = b"".join(trace().responses((0x9D, 0x04, dtype, 1, 1, 0, 0))[0])
            frames = [stream[i:i + 30] for i in range(0, len(stream) - 29, 30)]
            series[dtype] = decode_ed_subframes(frames, is_spo2=(dtype == 1))
        self.assertEqual(len(series[1]), 243)   # raw 2 Hz values
        self.assertEqual(len(records), 122)     # engine halves the rate: two raw values per record
        checked = 0
        # Two raw values per record; an odd final value is a record of its own (243 = 121 pairs + 1).
        def value(raw, i):
            return raw[2 * i + 1] if 2 * i + 1 < len(raw) else raw[2 * i]
        for i, rec in enumerate(records):
            self.assertEqual(rec["spo2"], round((series[1][2 * i] + value(series[1], i)) / 2.0), i)
            self.assertEqual(rec["heart_rate"], round((series[2][2 * i] + value(series[2], i)) / 2.0), i)

    def test_timestamps_follow_the_session_start_at_one_per_second(self):
        records = self.download()
        self.assertEqual(records[0]["timestamp"], "2026-09-06T10:00:46")
        self.assertEqual(records[-1]["timestamp"], "2026-09-06T10:02:47")

    def test_good_samples_are_not_blanked_at_page_end(self):
        """T1 (fixed): the last frame of a page has a non-zero MSB mask in byte 7, which the detector used
        to read as status flags ("searching,low-perfusion"), so the engine stored those samples as None."""
        records = self.download()
        self.assertEqual([r for r in records if r["spo2"] is None], [])

    def test_export_writes_every_record(self):
        records = self.download()
        with tempfile.TemporaryDirectory() as d:
            csv_path = export.export_records(records, output_filename=os.path.join(d, "r.csv"))
            with open(csv_path, newline="") as fh:
                self.assertEqual(len(list(csv.DictReader(fh))), 122)
            spo2_path = export.export_records(records, output_filename=os.path.join(d, "r.spo2"))
            with open(spo2_path, "rb") as fh:
                blob = fh.read()
        self.assertEqual(struct.unpack_from("<I", blob, 0x0438)[0], 122)
        self.assertEqual(len(blob), export.SPO2_HEADER_SIZE + 122 * 2)


class TestInfoFlow(FlowCase):
    def test_reads_clock_and_user_from_recorded_replies(self):
        res = self.engine.read_device_info()
        self.assertEqual(res["rtc_time_str"], "2002-07-01 12:07:00")
        self.assertEqual(res["device_info"].user_profile, "user")

    def test_unrecorded_queries_are_the_only_unanswered_ones(self):
        self.engine.read_device_info()
        self.assertEqual(self.unmatched_keys(), {(0xAD,), (0x9E, 0x40, 0x04)})


@unittest.skipUnless(LINUX, "LinuxHidrawBackend is Linux-only")
class TestFaults(unittest.TestCase):
    """What the CLI does when the device misbehaves."""

    def run_download(self, fault=None, unplug_after=None, extra=()):
        fake = fresh_fake(fault=fault)
        with tempfile.TemporaryDirectory() as d, HidrawSim(fake) as sim, VirtualClock().patch():
            if unplug_after is not None:
                orig = fake.handle_out

                def hooked(report):
                    orig(report)
                    if len(fake.sent) == unplug_after:
                        sim.unplug()
                fake.handle_out = hooked
            out_path = os.path.join(d, "out.csv")
            rc, out, err = run_cli(["download", "--backend", "hidraw", "-o", out_path, *extra])
            written = os.path.exists(out_path)
            rows = None
            if written:
                with open(out_path, newline="") as fh:
                    rows = len(list(csv.DictReader(fh)))
        return rc, out, err, written, rows, fake

    def test_normal_download_through_the_cli(self):
        rc, out, err, written, rows, fake = self.run_download()
        self.assertEqual(rc, 0)
        self.assertTrue(written)
        self.assertEqual(rows, 122)

    def test_unplugged_mid_download_fails_with_one_clear_line_and_writes_nothing(self):
        rc, out, err, written, rows, fake = self.run_download(unplug_after=7)
        self.assertEqual(rc, 1)
        self.assertFalse(written)
        self.assertIn("No such device", out + err)
        self.assertNotIn("Traceback", out + err)

    def test_unplugged_before_connecting_reports_no_device(self):
        fake = fresh_fake()
        with HidrawSim(fake, present=False), tempfile.TemporaryDirectory() as d:
            rc, out, err = run_cli(["download", "--backend", "hidraw", "-o", os.path.join(d, "o.csv")])
        self.assertEqual(rc, 1)
        self.assertIn("No Pulsox PO-400 device found", out + err)

    def test_dropped_page_frame_gives_fewer_records_without_crashing(self):
        def drop_last_report_of_pages(key, i, rep):
            return None if (key[:2] == (0x9D, 0x04) and i == 2) else rep
        rc, out, err, written, rows, fake = self.run_download(fault=drop_last_report_of_pages)
        self.assertEqual(rc, 0)
        self.assertLess(rows, 122)

    def test_device_that_never_answers_is_not_reported_as_a_successful_download(self):
        """T2 (fixed): with every reply dropped, `download` used to invent "Session #1 / 60 records",
        find nothing, save an empty file and exit 0. A dead or ignoring device is an error."""
        rc, out, err, written, rows, fake = self.run_download(fault=lambda key, i, rep: None)
        self.assertEqual(rc, 1)
        self.assertFalse(written)
        self.assertIn("No recording data was received", out + err)

    def test_info_does_not_print_made_up_values_when_the_device_is_silent(self):
        """T4 (fixed): `info` used to fall back to hard-coded firmware "v2.0", serial "50F", user and
        geometry when the device did not answer, so they looked like device readings."""
        fake = fresh_fake(fault=lambda key, i, rep: None)
        with HidrawSim(fake), VirtualClock().patch():
            rc, out, err = run_cli(["info", "--backend", "hidraw"])
        self.assertNotIn("v2.0", out)
        self.assertNotIn("50F", out)
        self.assertNotIn("Sub-chunk", out)
        for label in ("Firmware Version", "Serial Number", "User Profile String", "Storage Memory Geometry"):
            self.assertRegex(out, rf"{label}\s*: not reported by the device")

    def test_frame_with_a_bad_checksum_is_rejected(self):
        """T5 (fixed): the detector never verified the 7-bit checksum that every real frame carries."""
        stream = b"".join(trace().responses((0x9D, 0x04, 1, 1, 1, 0, 0))[0])
        frame = bytearray(stream[30:60])
        frame[10] ^= 0x01                       # flip a data bit, leave the checksum stale
        self.assertNotEqual(sum(frame[:29]) & 0x7F, frame[29])
        buf = SerialByteStreamBuffer()
        buf.write(bytes(frame))
        events = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual([e for e in events if e.packet_type == "STORED_BLOCK"], [])
        self.assertEqual([e.packet_type for e in events], ["CORRUPT_FRAME"])

    def test_download_with_a_corrupted_frame_warns_and_still_finishes(self):
        def corrupt(key, i, rep):
            if key[:2] == (0x9D, 0x04) and key[2] == 1 and i == 0:
                b = bytearray(rep)
                b[40] ^= 0x01                   # inside the second frame's data
                return bytes(b)
            return rep
        rc, out, err, written, rows, fake = self.run_download(fault=corrupt)
        self.assertEqual(rc, 0)
        self.assertIn("1 stored frame(s) failed their checksum", out)
        self.assertIn("Download it again", out)


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
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            recorded = record_exchange.record(dev, download=True)
            dev.close()
        self.assertEqual(fake.destructive, [])
        self.assertGreater(len(recorded.groups), 5)

        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rec.trace.json")
            recorded.to_json(p)
            replay = Trace.from_json(p)

        fake2 = FakeOximeter(replay)
        with HidrawSim(fake2), VirtualClock().patch(), contextlib.redirect_stdout(io.StringIO()):
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            engine = SerialDeviceEngine(dev)
            again = engine.download_session(engine.list_sessions()[0])
            dev.close()
        self.assertEqual(len(again), 122)

    def test_recorder_refuses_destructive_commands(self):
        import record_exchange
        fake = fresh_fake()
        with HidrawSim(fake):
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            rec = record_exchange.RecordingDevice(dev)
            with self.assertRaises(record_exchange.RefusedCommand):
                rec.write_report(Commands.build_hid(0xAA, [0x80, 0x80]))
            dev.close()
        self.assertEqual(fake.sent, [], "a refused command must never reach the device")


if __name__ == "__main__":
    unittest.main()
