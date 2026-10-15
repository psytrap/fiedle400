"""Mock-hardware tests driven by a recording of the CLI's own traffic with a real PO-400.

``tests/fixtures/cli-exchange.trace.json`` was made with
``tests/capture_tools/record_exchange.py`` on the Windows 8.1 laptop (hid backend,
read-only): 18 command exchanges and one stored session of 214 raw samples. Unlike the vendor-tool
capture used by ``test_hwsim_linux.py``, every command the CLI sends has a recorded answer,
so these flows run with ``FakeOximeter(strict=True)``: a request that was never recorded is
unanswered instead of being served from another request's data.

The defects this recording showed (RELEASE_PLAN.md section 3d, T1, T3, T4, T6, T7) were first pinned here as
expected failures; they are fixed and these tests now assert the correct behaviour.
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hwsim  # noqa: E402
from hwsim import FakeOximeter, HidrawSim, Trace, VirtualClock, command_key  # noqa: E402
import test_hwsim_linux as base  # noqa: E402  (module import only: its test classes are not collected here)

from fiedle400.engine import SerialDeviceEngine, SerialPacketDetector, SerialByteStreamBuffer  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402
from fiedle400.protocol.decompression import decode_ed_subframes, unmask_subframe_msb  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cli-exchange.trace.json")
PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "probe.trace.json")
SPO2, PULSE = 1, 2

_TRACE = None


def real_trace() -> Trace:
    global _TRACE
    if _TRACE is None:
        _TRACE = Trace.from_json(FIXTURE)
    return _TRACE


def probe_trace() -> Trace:
    """The same device, with SpO2 reads at offsets 0, 1, 2, 50, 107, 150, 213, 214, 215, 300 and the 80 00 query."""
    return Trace.from_json(PROBE)


def window(series: int, offset: int):
    """Raw 2 Hz samples of one stored-data reply, decoded independently of the engine."""
    stream = b"".join(real_trace().responses((0x9D, 0x04, series, 1, 1, offset, 0))[0])
    frames = [stream[i:i + 30] for i in range(0, len(stream) - 29, 30)]
    return decode_ed_subframes(frames, is_spo2=(series == SPO2))


def pairs(samples):
    """What the engine does with raw values: average two 2 Hz values into one 1 Hz record."""
    return [round((samples[2 * i] + samples[2 * i + 1]) / 2.0) for i in range(len(samples) // 2)]


# --------------------------------------------------------------------------
# The recording itself (platform neutral)
# --------------------------------------------------------------------------
class TestRecordedSession(unittest.TestCase):
    def test_covers_everything_the_cli_asks_for(self):
        keys = set(real_trace().keys())
        for needed in [("unlock",), (0x82,), (0xAD,), (0x81,), (0x8E, 3), (0x9E, 0x40, 0x04), (0x9C, 0x80), (0x9C, 1),
                       (0x9D, 2), (0x9D, 4, 1, 1, 1, 0, 0), (0x9D, 4, 2, 1, 1, 2, 0)]:
            self.assertIn(needed, keys)
        self.assertEqual(len(real_trace().groups), 18)

    def test_bare_acks_are_all_the_device_says_to_the_firmware_serial_and_geometry_queries(self):
        """T4/T7: 0xAD and 0x9E are answered with `f0 70` and nothing else."""
        for key in ((0xAD,), (0x9E, 0x40, 0x04)):
            (group,) = real_trace().responses(key)
            self.assertEqual(len(group), 1)
            self.assertEqual(group[0][:2], bytes([0xF0, 0x70]))
            self.assertEqual(group[0][2:], bytes(62), key)

    def test_the_0x81_query_is_answered_with_the_model_descriptor_in_an_0xf1_report(self):
        (group,) = real_trace().responses((0x81,))
        self.assertEqual(group[0][0], 0xF1)
        self.assertEqual(group[0][1:4], b"50F")

    def test_header_reports_214_raw_samples_for_session_1_started_2026_09_30(self):
        (group,) = real_trace().responses((0x9C, 1))
        hdr = group[0]
        self.assertEqual(hdr[0], 0xEC)
        self.assertEqual(tuple(hdr[4:10]), (26, 9, 30, 19, 54, 53))

    def test_every_stored_frame_has_a_valid_checksum(self):
        checked = 0
        for series in (SPO2, PULSE):
            for offset in (0, 1, 2):
                stream = b"".join(real_trace().responses((0x9D, 4, series, 1, 1, offset, 0))[0])
                self.assertEqual(len(stream), 192)
                for i in range(0, 180, 30):   # six frames, then padding to three 64-byte reports
                    frame = stream[i:i + 30]
                    self.assertEqual(sum(frame[:29]) & 0x7F, frame[29], (series, offset, i))
                    checked += 1
        self.assertEqual(checked, 36)

    def test_the_page_number_is_a_sample_offset_each_reply_is_the_session_shifted_by_that_many_samples(self):
        """T6: page k returns the same session starting k raw samples in (214, 213, 212 values)."""
        for series in (SPO2, PULSE):
            w0, w1, w2 = (window(series, k) for k in (0, 1, 2))
            self.assertEqual((len(w0), len(w1), len(w2)), (214, 213, 212))
            self.assertEqual(w1, w0[1:])
            self.assertEqual(w2, w0[2:])

    def test_the_probe_recording_confirms_offsets_in_raw_samples_up_to_the_end_of_the_data(self):
        """Each reply is the session from that raw sample to the end (both for 50, 107, 150 and 213)."""
        full = window(SPO2, 0)
        for off, count in ((1, 213), (50, 164), (107, 107), (150, 64), (213, 1)):
            stream = b"".join(probe_trace().responses((0x9D, 4, SPO2, 1, 1, off & 0x7F, off >> 7))[0])
            frames = [stream[i:i + 30] for i in range(0, len(stream) - 29, 30)]
            got = decode_ed_subframes(frames, is_spo2=True)
            self.assertEqual((len(got), got == full[off:]), (count, True), off)

    def test_the_last_frame_of_a_reply_is_a_short_filler_frame_whose_mask_bytes_are_0x7f(self):
        stream = b"".join(real_trace().responses((0x9D, 4, SPO2, 1, 1, 0, 0))[0])
        last = stream[150:180]
        self.assertEqual((last[3], last[7]), (5, 0x7F))
        self.assertEqual(len(decode_ed_subframes([last], is_spo2=True)), 8)


# --------------------------------------------------------------------------
# Whole flows on the Linux hidraw path with the recording
# --------------------------------------------------------------------------
class RealFlow(base.FlowCase):
    def make_fake(self):
        return FakeOximeter(real_trace(), strict=True)

    def assert_fully_answered(self):
        self.assertEqual([r.hex()[:24] for r in self.fake.unmatched], [])
        self.assertEqual(self.fake.destructive, [])


class TestSessions(RealFlow):
    def test_lists_the_recorded_session(self):
        (s,) = self.engine.list_sessions()
        self.assertEqual((s.session_id, s.user_id, s.record_count, s.raw_samples), (1, 1, 107, 214))
        self.assertEqual(s.timestamp.isoformat(), "2026-09-30T19:54:53")
        self.assert_fully_answered()

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual([command_key(r) for r in self.fake.sent], [("unlock",), (0x9C, 0x80), (0x9C, 1)])

    def test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds(self):
        """T3 (fixed) on real data: 214 raw samples at 2 Hz are 107 s, and the independent decode of the
        first reply agrees (214 values, 107 averaged records)."""
        (s,) = self.engine.list_sessions()
        self.assertEqual(s.duration_seconds, 107)
        self.assertEqual(s.duration_str, "1m 47s")


class TestDownload(RealFlow):
    def keys_sent(self):
        out = []
        for r in self.fake.sent:
            k = command_key(r)
            if not out or out[-1] != k:
                out.append(k)
        return out

    def test_command_sequence_reads_the_session_in_one_window(self):
        self.download()
        page = lambda s, k: (0x9D, 4, s, 1, 1, k, 0)  # noqa: E731
        self.assertEqual(self.keys_sent(), [
            ("unlock",), (0x9C, 0x80), (0x9C, 1),
            ("unlock",), (0x9D, 2),
            page(SPO2, 0), page(PULSE, 0),
            (0x9D, 2),
        ])
        self.assert_fully_answered()

    def test_ends_with_the_non_destructive_segment_ack(self):
        self.download()
        self.assertEqual(command_key(self.fake.sent[-1]), (0x9D, 2))

    def test_no_retries_when_every_request_is_answered(self):
        self.download()
        self.assertEqual(len(self.fake.sent), 8)

    def test_each_sample_of_the_session_is_exported_once(self):
        """T6/T1/T3 (fixed): a 214-sample session is 107 one-second records, the averaged pairs of the
        first reply. The engine used to ask for windows 1 and 2 as well and export 214 records."""
        records = self.download()
        self.assertEqual([r["spo2"] for r in records], pairs(window(SPO2, 0)))
        self.assertEqual([r["heart_rate"] for r in records], pairs(window(PULSE, 0)))
        self.assertEqual([r["flags"] for r in records], ["ok"] * 107)
        self.assertEqual(records[-1]["timestamp"], "2026-09-30T19:56:39")

    def test_no_samples_are_lost_at_the_end_of_a_window(self):
        """T1 (fixed): the short filler frame at the end of a reply (mask bytes 0x7f) holds the last 4
        pairs. Its byte 7 is the third MSB mask, not a status field."""
        stream = b"".join(real_trace().responses((0x9D, 4, SPO2, 1, 1, 0, 0))[0])
        SerialPacketDetector.reset_decoder_state()
        buf = SerialByteStreamBuffer()
        buf.write(stream)
        events = [e for e in SerialPacketDetector.detect_and_decode_stream(buf) if e.packet_type == "STORED_BLOCK"]
        self.assertEqual(sum(e.spo2 is not None for e in events), 107)
        self.assertEqual({e.status_str for e in events}, {"ok"})


class TestDownloadPastTheEnd(RealFlow):
    """The probe recording also holds the reply at offset 214, the first offset past the data."""

    def make_fake(self):
        return FakeOximeter(probe_trace().with_header_samples(400), strict=True)

    def test_the_header_may_claim_more_than_the_device_holds_the_end_marker_stops_the_download(self):
        """Offset == stored samples is answered with an end marker (one frame of 0xFF filler), not with
        silence. A header announcing 400 samples must not make the engine loop or invent records."""
        records = self.download()
        self.assertEqual(len(records), 107)
        keys = [command_key(r) for r in self.fake.sent if command_key(r)[:3] == (0x9D, 4, SPO2)]
        offsets = [k[5] | k[6] << 7 for k in keys]
        self.assertEqual(sorted(set(offsets)), [0, 214])
        self.assertEqual(offsets.count(214), 3, "an answer without samples reads as silence: one request plus two retries")
        self.assertEqual(self.fake.destructive, [])

    def test_the_end_marker_is_a_frame_of_0xff_filler_and_offsets_beyond_it_are_not_answered(self):
        end = probe_trace().responses((0x9D, 4, SPO2, 1, 1, 214 & 0x7F, 214 >> 7))[0]
        self.assertEqual(end[0][:8].hex(), "ed0401000" + "07b7f7f"[0:7])
        self.assertEqual(unmask_subframe_msb(end[0][:30])[:2], bytearray(b"\xff\xff"))   # decodes to the terminator
        for off in (215, 300):
            self.assertEqual(probe_trace().responses((0x9D, 4, SPO2, 1, 1, off & 0x7F, off >> 7)), [[]], off)


class TestInfo(RealFlow):
    def test_clock_and_user_come_from_recorded_replies(self):
        res = self.engine.read_device_info()
        self.assertEqual(res["rtc_time_str"], "2002-07-01 12:07:00")
        self.assertEqual(res["device_info"].user_profile, "user")
        self.assert_fully_answered()

    def run_info(self):
        fake = FakeOximeter(real_trace(), strict=True)
        with HidrawSim(fake), VirtualClock().patch():
            return base.run_cli(["info", "--backend", "hidraw"])

    def info_lines(self):
        rc, out, err = self.run_info()
        self.assertEqual(rc, 0)
        return dict((k.strip(), v.strip()) for k, _, v in (l.partition(":") for l in out.splitlines()) if v)

    def test_firmware_serial_and_geometry_are_not_made_up(self):
        """T4/T7 (fixed): the device answers 0xAD and 0x9E with a bare ACK (and 0x80 too, see the probe
        recording), so there is nothing to print. `info` used to show 'v2.0 (CMS-60D/PO-400 v2)' and
        '112 Bytes Sub-chunk Payload', which is the ACK status byte 0x70."""
        lines = self.info_lines()
        for label in ("Firmware Version", "Serial Number", "Storage Memory Geometry"):
            self.assertEqual(lines[label], "not reported by the device", label)

    def test_the_model_descriptor_is_shown_as_such_and_the_user_comes_from_the_device(self):
        """The 0xF1 reply to 0x81 is the hardware model descriptor ('50F', PROTOCOL.md)."""
        lines = self.info_lines()
        self.assertEqual(lines["Device Model Descriptor"], "50F")
        self.assertEqual(lines["User Profile String"], "user")
        self.assertEqual(lines["Device RTC Timestamp"], "2002-07-01 12:07:00")

    def test_the_probe_recording_shows_80_00_is_also_only_acknowledged(self):
        (group,) = probe_trace().responses((0x80,))
        self.assertEqual(group[0][:2], bytes([0xF0, 0x70]))
        self.assertEqual(group[0][2:], bytes(62))


# --------------------------------------------------------------------------
# Finger out: the stream marks it with out-of-range values, not with a flag byte (T1)
# --------------------------------------------------------------------------
def stored_frame(series: int, seq: int, data: bytes) -> bytes:
    """A 30-byte 0xED frame: header, three MSB masks, 21 data bytes (0xFF padded), 7-bit checksum."""
    data = bytes(data) + b"\xff" * (21 - len(data))
    masks = [0, 0, 0]
    low = bytearray()
    for i, b in enumerate(data):
        if b & 0x80:
            masks[i // 7] |= 1 << (i % 7)
        low.append(b & 0x7F)
    body = bytes([0xED, 0x04, series, seq & 0x7F, seq >> 7, *masks]) + bytes(low)
    return body + bytes([sum(body) & 0x7F])


def reply_reports(frame: bytes):
    raw = frame + bytes(-len(frame) % 64)
    return [raw[i:i + 64] for i in range(0, len(raw), 64)]


class TestFingerOut(unittest.TestCase):
    def detect(self, series, data):
        SerialPacketDetector.reset_decoder_state()
        buf = SerialByteStreamBuffer()
        buf.write(stored_frame(series, 0, data))
        return [e for e in SerialPacketDetector.detect_and_decode_stream(buf) if e.packet_type == "STORED_BLOCK"]

    def test_out_of_range_spo2_is_an_invalid_sample_not_a_status_flag(self):
        # base 127 (0xF7 0xFF), two 127s; base 98 (0xF6 0xF2), two 98s
        events = self.detect(SPO2, bytes([0xF7, 0xFF, 0x00, 0xF6, 0xF2, 0x00]))
        self.assertEqual([(e.spo2, e.invalid_sample, e.status_str) for e in events],
                         [(None, True, "probe-out"), (98, False, "ok")])

    def test_status_byte_values_in_the_mask_position_do_not_change_the_result(self):
        frame = bytearray(stored_frame(SPO2, 0, bytes([0xF6, 0xF2, 0x00, 0x11])))
        frame[7] |= 0x70            # m2 with bits for data bytes that are 0xFF padding anyway
        frame[29] = sum(frame[:29]) & 0x7F
        SerialPacketDetector.reset_decoder_state()
        buf = SerialByteStreamBuffer()
        buf.write(bytes(frame))
        events = [e for e in SerialPacketDetector.detect_and_decode_stream(buf) if e.packet_type == "STORED_BLOCK"]
        self.assertEqual({e.status_str for e in events}, {"ok"})

    @unittest.skipUnless(base.LINUX, "LinuxHidrawBackend is Linux-only")
    def test_download_gives_empty_records_for_the_finger_out_seconds(self):
        t = Trace()
        for out, key, ins in real_trace().with_header_samples(4).groups:
            if key[:2] != (0x9D, 4):
                t.add(out, ins)
        from fiedle400.protocol import Commands
        t.add(Commands.session_page(1, 1, 0, 1), reply_reports(stored_frame(SPO2, 0, bytes([0xF7, 0xFF, 0x00, 0xF6, 0xF2, 0x00]))))
        t.add(Commands.session_page(2, 1, 0, 1), reply_reports(stored_frame(PULSE, 0, bytes([0xF4, 0xF6, 0x00, 0x00]))))
        fake = FakeOximeter(t, strict=True)
        with HidrawSim(fake), VirtualClock().patch(), contextlib.redirect_stdout(io.StringIO()):
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            engine = SerialDeviceEngine(dev)
            records = engine.download_session(engine.list_sessions()[0])
            dev.close()
        self.assertEqual(fake.unmatched, [])
        self.assertEqual([(r["spo2"], r["heart_rate"], r["flags"]) for r in records],
                         [(None, None, "probe-out"), (98, 70, "ok")])
        self.assertEqual([r["timestamp"][-8:] for r in records], ["19:54:53", "19:54:54"])


# --------------------------------------------------------------------------
# The recorder, replayed against the recording
# --------------------------------------------------------------------------
class TestRecorderRoundTrip(unittest.TestCase):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))

    @unittest.skipUnless(base.LINUX, "LinuxHidrawBackend is Linux-only")
    def test_recording_the_cli_against_the_recording_reproduces_it(self):
        import record_exchange
        fake = FakeOximeter(real_trace(), strict=True)
        with HidrawSim(fake), VirtualClock().patch(), contextlib.redirect_stdout(io.StringIO()):
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            again = record_exchange.record(dev, download=True)
            dev.close()
        self.assertEqual(fake.unmatched, [])
        # The fixture predates the offset fix and holds windows 1 and 2, which the CLI no longer asks for;
        # everything it does ask for is recorded back byte for byte.
        original = {(k, tuple(ins)) for _, k, ins in real_trace().groups}
        for _, k, ins in again.groups:
            self.assertIn((k, tuple(ins)), original, k)
        self.assertEqual([k for _, k, _ in again.groups],
                         [k for _, k, _ in real_trace().groups if not (k[:2] == (0x9D, 4) and k[5] in (1, 2))])

if __name__ == "__main__":
    unittest.main()
