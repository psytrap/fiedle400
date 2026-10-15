"""Mock-hardware tests driven by a recording of the CLI's own traffic with a real PO-400.

``tests/fixtures/cli-exchange.trace.json`` was made with
``tests/capture_tools/record_exchange.py`` on the Windows 8.1 laptop (hid backend,
read-only): 18 command exchanges and one stored session of 214 raw samples. Unlike the vendor-tool
capture used by ``test_hwsim_linux.py``, every command the CLI sends has a recorded answer,
so these flows run with ``FakeOximeter(strict=True)``: a request that was never recorded is
unanswered instead of being served from another request's data.

Tests marked ``expectedFailure`` pin defects this recording shows (RELEASE_PLAN.md section 3d).
They fail today by design; when a defect is fixed its test starts passing, the suite reports an
"unexpected success", and the marker should be removed. Tests named ``*_today`` describe current
behaviour that is wrong or accidental; delete them together with the fix.
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
from fiedle400.protocol.decompression import decode_ed_subframes  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cli-exchange.trace.json")
SPO2, PULSE = 1, 2

_TRACE = None


def real_trace() -> Trace:
    global _TRACE
    if _TRACE is None:
        _TRACE = Trace.from_json(FIXTURE)
    return _TRACE


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
        self.assertEqual((s.session_id, s.user_id, s.record_count), (1, 1, 214))
        self.assertEqual(s.timestamp.isoformat(), "2026-09-30T19:54:53")
        self.assert_fully_answered()

    def test_sends_unlock_reset_then_query(self):
        self.engine.list_sessions()
        self.assertEqual([command_key(r) for r in self.fake.sent], [("unlock",), (0x9C, 0x80), (0x9C, 1)])

    @unittest.expectedFailure
    def test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds(self):
        """T3 on real data: 214 raw samples at 2 Hz are 107 s, and the independent decode of the
        first reply agrees (214 values, 107 averaged records)."""
        (s,) = self.engine.list_sessions()
        self.assertEqual(s.duration_seconds, 107)


class TestDownload(RealFlow):
    def keys_sent(self):
        out = []
        for r in self.fake.sent:
            k = command_key(r)
            if not out or out[-1] != k:
                out.append(k)
        return out

    def test_command_sequence_requests_three_overlapping_windows(self):
        self.download()
        page = lambda s, k: (0x9D, 4, s, 1, 1, k, 0)  # noqa: E731
        self.assertEqual(self.keys_sent(), [
            ("unlock",), (0x9C, 0x80), (0x9C, 1),
            ("unlock",), (0x9D, 2),
            page(SPO2, 0), page(PULSE, 0), page(SPO2, 1), page(PULSE, 1), page(SPO2, 2), page(PULSE, 2),
            (0x9D, 2),
        ])
        self.assert_fully_answered()

    def test_ends_with_the_non_destructive_segment_ack(self):
        self.download()
        self.assertEqual(command_key(self.fake.sent[-1]), (0x9D, 2))

    def test_no_retries_when_every_request_is_answered(self):
        self.download()
        self.assertEqual(len(self.fake.sent), 12)

    def test_first_window_is_decoded_like_the_independent_decompression_for_103_records_today(self):
        records = self.download()
        want_spo2, want_hr = pairs(window(SPO2, 0)), pairs(window(PULSE, 0))
        self.assertEqual(len(want_spo2), 107)
        self.assertEqual([r["spo2"] for r in records[:103]], want_spo2[:103])
        self.assertEqual([r["heart_rate"] for r in records[:103]], want_hr[:103])

    def test_download_today_returns_214_records_that_repeat_the_session_three_times_over(self):
        """T6 characterisation: the true session is 107 records. Records 103..205 are window 1
        (the same session starting one raw sample later) and 206..213 are the start of window 2."""
        records = self.download()
        self.assertEqual(len(records), 214)
        self.assertEqual([r["spo2"] for r in records[103:206]], pairs(window(SPO2, 1))[:103])
        self.assertEqual([r["spo2"] for r in records[206:]], pairs(window(SPO2, 2))[:8])
        self.assertEqual([r["heart_rate"] for r in records[103:206]], pairs(window(PULSE, 1))[:103])
        self.assertEqual([r["spo2"] for r in records[103:113]], [r["spo2"] for r in records[0:10]])
        self.assertEqual([r["flags"] for r in records], ["ok"] * 214)

    def test_the_last_frame_of_a_window_is_read_as_probe_out_today(self):
        """T1 on real data: the filler frame (mask bytes 0x7f) is classified from byte 7 as
        `probe-out,searching,low-perfusion`, so its 4 averaged pairs are never decoded."""
        stream = b"".join(real_trace().responses((0x9D, 4, SPO2, 1, 1, 0, 0))[0])
        SerialPacketDetector.reset_decoder_state()
        buf = SerialByteStreamBuffer()
        buf.write(stream)
        events = [e for e in SerialPacketDetector.detect_and_decode_stream(buf) if e.packet_type == "STORED_BLOCK"]
        self.assertEqual(sum(e.spo2 is not None for e in events), 103)
        self.assertIn("probe-out", events[-1].status_str)

    @unittest.expectedFailure
    def test_no_samples_are_lost_at_the_end_of_a_window(self):
        """T1: all 107 pairs of the first reply should be decoded."""
        stream = b"".join(real_trace().responses((0x9D, 4, SPO2, 1, 1, 0, 0))[0])
        SerialPacketDetector.reset_decoder_state()
        buf = SerialByteStreamBuffer()
        buf.write(stream)
        events = [e for e in SerialPacketDetector.detect_and_decode_stream(buf) if e.packet_type == "STORED_BLOCK"]
        self.assertEqual(sum(e.spo2 is not None for e in events), 107)

    @unittest.expectedFailure
    def test_each_sample_of_the_session_is_exported_once(self):
        """T6 (with T1 and T3): a 214-sample session is 107 one-second records, the averaged pairs
        of the first reply, and the engine asks for no further window."""
        records = self.download()
        self.assertEqual([r["spo2"] for r in records], pairs(window(SPO2, 0)))
        self.assertEqual([r["heart_rate"] for r in records], pairs(window(PULSE, 0)))


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

    @unittest.expectedFailure
    def test_firmware_line_is_not_a_hard_coded_fallback(self):
        """T4: the device never reported a firmware version (0xAD gives a bare ACK, the 0x81 reply is the
        model descriptor and the code ignores it), yet `info` prints 'v2.0 (CMS-60D/PO-400 v2)'."""
        rc, out, err = self.run_info()
        self.assertEqual(rc, 0)
        self.assertNotIn("v2.0 (CMS-60D/PO-400 v2)", out)

    @unittest.expectedFailure
    def test_model_descriptor_is_not_labelled_serial_number(self):
        """T4: the 0xF1 reply to 0x81 is the hardware model descriptor ('50F', PROTOCOL.md), but
        `parse_serial` stores it as the serial number."""
        rc, out, err = self.run_info()
        self.assertNotRegex(out, r"Serial Number\s*:\s*50F")

    @unittest.expectedFailure
    def test_geometry_is_not_derived_from_the_ack_byte(self):
        """T7: the device answers 0x9E with `f0 70`; the parser reads 0x70 = 112 as a 'sub-chunk payload'."""
        rc, out, err = self.run_info()
        self.assertNotIn("112 Bytes Sub-chunk Payload", out)


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
        self.assertEqual([k for _, k, _ in again.groups], [k for _, k, _ in real_trace().groups])
        self.assertEqual([ins for _, _, ins in again.groups], [ins for _, _, ins in real_trace().groups])

    @unittest.skipUnless(base.LINUX, "LinuxHidrawBackend is Linux-only")
    def test_probes_record_unanswered_questions_as_empty_replies_and_stay_read_only(self):
        import record_exchange
        fake = FakeOximeter(real_trace(), strict=True)
        clock = VirtualClock()
        with HidrawSim(fake), clock.patch(), contextlib.redirect_stdout(io.StringIO()):
            dev = PulsoxHidDevice(backend="hidraw")
            dev.connect()
            probe = record_exchange.record(dev, download=False, offsets=[0, 1, 2, 3], firmware=True, clock=clock)
            dev.close()
        self.assertEqual(fake.destructive, [])
        replies = {k: [len(i) for i in ins] for _, k, ins in probe.groups if k and k[0] == 0x9D and k[1] == 4}
        self.assertEqual(replies, {(0x9D, 4, 1, 1, 1, 0, 0): [64, 64, 64], (0x9D, 4, 1, 1, 1, 1, 0): [64, 64, 64],
                                   (0x9D, 4, 1, 1, 1, 2, 0): [64, 64, 64], (0x9D, 4, 1, 1, 1, 3, 0): []})
        self.assertEqual(command_key(probe.groups[-1][0]), (0x9D, 2))     # ends with the usual ack
        firmware = [ins for _, k, ins in probe.groups if k == (0x80,)]
        self.assertEqual(firmware, [[]])                                    # not in this recording: unanswered
        self.assertEqual(set(command_key(r) for r in fake.unmatched), {(0x80,), (0x9D, 4, 1, 1, 1, 3, 0)})

    def test_offsets_option_is_validated(self):
        import record_exchange
        self.assertEqual(record_exchange.parse_offsets("0, 1,214"), [0, 1, 214])
        for bad in ("", "-1", "16384", "a"):
            with self.assertRaises(ValueError, msg=bad):
                record_exchange.parse_offsets(bad)


if __name__ == "__main__":
    unittest.main()
