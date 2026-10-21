"""Manual-mode recordings (T-042, PROTOCOL.md 3.14), against SpO2 Assistant's own download.

``tests/fixtures/manual-download.trace.json`` holds the manual-mode exchanges of
``archive/capture/bum400_20261015_194301.pcap`` (psytrap, 2026-10-15): one recording,
2026-10-15 19:34:16, 59 samples, read with A0 / A3 / A7 / A2. The device in that capture was
never asked 0x9C, so in these flows the CLI's session queries go unanswered, as an empty
Auto list would.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import FakeOximeter, Trace, command_key  # noqa: E402
import test_hwsim_linux as base  # noqa: E402

from fiedle400.protocol import manual  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "manual-download.trace.json")


def trace() -> Trace:
    return Trace.from_json(FIXTURE)


def reply(key):
    (group,) = trace().responses(key)
    return manual.frames(group)


def sent_by_vendor(op):
    return [o for o, _, _ in trace().groups if o[0] == op]


class TestFrames(unittest.TestCase):
    def test_header_is_the_recording_of_2026_10_15_with_59_samples(self):
        (frame,) = reply((0xA0, 0))
        h = manual.parse_header(frame)
        self.assertEqual(h.start.isoformat(), "2026-10-15T19:34:16")
        self.assertEqual((h.samples, h.kind), (59, 0))

    def test_header_with_a_wrong_checksum_is_ignored(self):
        (frame,) = reply((0xA0, 0))
        self.assertIsNone(manual.parse_header(frame[:13] + bytes([(frame[13] + 1) & 0x7F])))

    def test_one_report_holds_three_subframes_numbered_0_to_2(self):
        for key, op in (((0xA3, 0, 0, 0), manual.SPO2_DATA), ((0xA2, 0, 0, 0), manual.PULSE_DATA)):
            frames = reply(key)
            self.assertEqual([(f[0], manual.subframe_seq(f)) for f in frames], [(op, 0), (op, 1), (op, 2)])

    def test_spo2_decodes_like_spo2_exe_27_values_per_subframe(self):
        s = [manual.decode_subframe(f) for f in reply((0xA3, 0, 0, 0))]
        self.assertEqual(s[0], [0x7F] * 27)                      # no finger
        self.assertEqual(s[1], [96] * 5 + [97] * 9 + [0x7F] * 13)  # ends on the 0xF nibble
        self.assertEqual(s[2], [0x7F] * 27)

    def test_pulse_decodes_like_spo2_exe(self):
        p = [manual.decode_subframe(f) for f in reply((0xA2, 0, 0, 0))]
        self.assertEqual(p[1][:15], [57, 63, 69] + [71] * 11 + [0xFF])
        # A pulse of 0x7F (127) is in range, so the no-finger subframes decode to noise (127, 134,
        # then 0xFF + 7 wrapping to 6): records() takes pulse only where SpO2 is valid.
        self.assertEqual(p[0][:4], [127, 134, 0xFF, 6])
        self.assertEqual(manual.records(*[sum(x, []) for x in (
            [manual.decode_subframe(f) for f in reply((0xA3, 0, 0, 0))], p)], 59)[:2], [(None, None)] * 2)

    def test_the_commands_are_byte_for_byte_what_spo2_assistant_sends(self):
        self.assertEqual(manual.header_query(), sent_by_vendor(0xA0)[0])
        self.assertEqual(manual.series_request(manual.SPO2_REQUEST), sent_by_vendor(0xA3)[0])
        self.assertEqual(manual.series_end(manual.SPO2_REQUEST), sent_by_vendor(0xA3)[1])
        self.assertEqual(manual.series_request(manual.PULSE_REQUEST), sent_by_vendor(0xA2)[0])
        self.assertEqual(manual.series_end(manual.PULSE_REQUEST), sent_by_vendor(0xA2)[1])
        self.assertEqual([manual.block_ack(True), manual.block_ack(False)], sent_by_vendor(0xA7))

    def test_a_resume_request_carries_the_subframe_number_in_7_bit_halves(self):
        self.assertEqual(manual.series_request(manual.SPO2_REQUEST, 130)[:5], bytes([0xA3, 0, 2, 1, (0xA3 + 3) & 0x7F]))


class ManualFlow(base.FlowCase):
    def make_fake(self):
        return FakeOximeter(trace(), strict=True)

    def keys_sent(self):
        return [command_key(r) for r in self.fake.sent]


class TestManualSessions(ManualFlow):
    def test_lists_the_manual_recording_when_the_auto_list_is_empty(self):
        (s,) = self.engine.list_sessions()
        self.assertTrue(s.manual)
        self.assertEqual((s.session_id, s.record_count, s.duration_str), (1, 59, "59s"))
        self.assertEqual(s.timestamp.isoformat(), "2026-10-15T19:34:16")
        self.assertEqual(self.keys_sent(), [("unlock",), (0x9C, 0x80), (0x9C, 1), (0xA0, 0)])


class TestManualDownload(ManualFlow):
    def test_sends_spo2_assistants_sequence_and_nothing_destructive(self):
        self.download()
        self.assertEqual(self.keys_sent()[4:], [
            (0x80,), (0xA3, 0, 0, 0), (0xA7, 1), (0xA2, 0, 0, 0), (0xA7, 0), (0xA3, 0x7F, 0, 0), (0xA2, 0x7F, 0, 0)])
        self.assertEqual(self.fake.destructive, [])

    def test_59_one_second_records_with_the_finger_in_from_second_27_to_40(self):
        records = self.download()
        self.assertEqual(len(records), 59)
        self.assertEqual(records[0]["timestamp"], "2026-10-15T19:34:16")
        self.assertEqual(records[-1]["timestamp"], "2026-10-15T19:35:14")
        valid = [i for i, r in enumerate(records) if r["spo2"] is not None]
        self.assertEqual(valid, list(range(27, 41)))
        self.assertEqual([records[i]["spo2"] for i in valid], [96] * 5 + [97] * 9)
        self.assertEqual([records[i]["heart_rate"] for i in valid], [57, 63, 69] + [71] * 11)
        self.assertTrue(all(r["flags"] == "probe-out" and r["heart_rate"] is None
                            for i, r in enumerate(records) if i not in valid))


class TestManualDownloadResumes(ManualFlow):
    def make_fake(self):
        dropped = []

        def lose_first_spo2_reply(key, i, rep):
            if key == (0xA3, 0, 0, 0) and not dropped:
                dropped.append(rep)
                return None
            return rep
        return FakeOximeter(trace(), fault=lose_first_spo2_reply)

    def test_a_lost_reply_is_asked_for_again_from_the_missing_subframe(self):
        records = self.download()
        keys = self.keys_sent()
        self.assertEqual(keys[5:8], [(0xA3, 0, 0, 0), (0xA3, 0x7F, 0, 0), (0xA3, 0, 0, 0)])
        self.assertEqual(sum(r["spo2"] is not None for r in records), 14)


class TestAutoDevicesAreNotAskedForManualHeaders(base.FlowCase):
    def test_a_device_with_auto_sessions_gets_no_a0(self):
        self.engine.list_sessions()
        self.assertNotIn(0xA0, self.fake.opcodes_sent())


if __name__ == "__main__":
    unittest.main()
