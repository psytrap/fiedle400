"""Unit tests for the Contec / PO-400 .SpO2 binary format and export module."""

import os
import struct
import tempfile
import unittest
from datetime import datetime

from fiedle400.export import (
    SPO2_HEADER_SIZE,
    SPO2_MAGIC,
    SPO2_VERSION,
    SPO2_CHANNEL_FLAG,
    SPO2_TAG_BLE,
    SPO2_INVALID_SPO2,
    SPO2_INVALID_HR,
    build_spo2_binary,
    export_records,
    pad_records,
)

# Also import the reference decoder to test round-trip compatibility
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))
from decode_spo2 import parse_header, parse_samples


class TestExportSpO2(unittest.TestCase):
    def setUp(self):
        self.start_dt = datetime(2026, 9, 30, 20, 15, 30)
        self.sample_records = [
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 1, "timestamp": "2026-09-30T20:15:30", "spo2": 98, "heart_rate": 72, "flags": "ok"},
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 2, "timestamp": "2026-09-30T20:15:31", "spo2": 97, "heart_rate": 71, "flags": "ok"},
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 3, "timestamp": "2026-09-30T20:15:32", "spo2": None, "heart_rate": None, "flags": "probe-out"},
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 4, "timestamp": "2026-09-30T20:15:33", "spo2": 99, "heart_rate": 75, "flags": "ok"},
        ]

    def test_build_spo2_binary_header_structure(self):
        data = build_spo2_binary(self.sample_records, start_dt=self.start_dt)
        self.assertEqual(len(data), SPO2_HEADER_SIZE + len(self.sample_records) * 2)

        # 0x0000: Magic
        magic = struct.unpack_from("<I", data, 0x0000)[0]
        self.assertEqual(magic, SPO2_MAGIC)
        self.assertEqual(magic, 0x0358)

        # 0x0004: Version
        ver = struct.unpack_from("<I", data, 0x0004)[0]
        self.assertEqual(ver, SPO2_VERSION)
        self.assertEqual(ver, 1)

        # 0x0358: Channel flag
        flag = struct.unpack_from("<I", data, 0x0358)[0]
        self.assertEqual(flag, SPO2_CHANNEL_FLAG)

        # 0x0360: BLE tag
        tag = data[0x0360:0x0366]
        self.assertEqual(tag, SPO2_TAG_BLE)

        # 0x0420: Datetime block
        y, m, d, H, M, S, count = struct.unpack_from("<7I", data, 0x0420)
        self.assertEqual(y, 2026)
        self.assertEqual(m, 9)
        self.assertEqual(d, 30)
        self.assertEqual(H, 20)
        self.assertEqual(M, 15)
        self.assertEqual(S, 30)
        self.assertEqual(count, 4)

    def test_build_spo2_binary_payload_and_sentinels(self):
        data = build_spo2_binary(self.sample_records, start_dt=self.start_dt)
        payload = data[SPO2_HEADER_SIZE:]

        # Sample 1: 98, 72
        self.assertEqual(payload[0], 98)
        self.assertEqual(payload[1], 72)

        # Sample 2: 97, 71
        self.assertEqual(payload[2], 97)
        self.assertEqual(payload[3], 71)

        # Sample 3: None, None -> Sentinels 127 (0x7F) and 255 (0xFF)
        self.assertEqual(payload[4], SPO2_INVALID_SPO2)
        self.assertEqual(payload[4], 127)
        self.assertEqual(payload[5], SPO2_INVALID_HR)
        self.assertEqual(payload[5], 255)

        # Sample 4: 99, 75
        self.assertEqual(payload[6], 99)
        self.assertEqual(payload[7], 75)

    def test_mixed_channel_validity_synchronizes_to_sentinel_pair(self):
        """T-004: OSCAR's probe-out check is `o2 == 0x7f AND pr == 0xff` (SPO2_FORMAT.md
        §5.2) -- it never treats one channel as probe-out on its own. A record where only
        one channel is invalid (spo2 decoded but heart_rate missing/out-of-range, or the
        reverse) must still write the sentinel pair for BOTH bytes, never a mixed pair
        that OSCAR would import as a literal value on the "valid" channel.
        """
        mixed_records = [
            # SpO2 decoded fine, heart rate missing (e.g. no prior fallback yet).
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 1, "timestamp": "2026-09-30T20:15:30", "spo2": 98, "heart_rate": None, "flags": "ok"},
            # Heart rate decoded fine, SpO2 out of physiological range.
            {"session_id": 1, "user_id": 1, "block_id": 1, "seq": 2, "timestamp": "2026-09-30T20:15:31", "spo2": 0, "heart_rate": 72, "flags": "ok"},
        ]
        data = build_spo2_binary(mixed_records, start_dt=self.start_dt)
        payload = data[SPO2_HEADER_SIZE:]

        # Sample 1: spo2 valid, heart_rate None -> both bytes sentinel.
        self.assertEqual(payload[0], SPO2_INVALID_SPO2)
        self.assertEqual(payload[1], SPO2_INVALID_HR)

        # Sample 2: heart_rate valid, spo2 out of range -> both bytes sentinel.
        self.assertEqual(payload[2], SPO2_INVALID_SPO2)
        self.assertEqual(payload[3], SPO2_INVALID_HR)

    def test_round_trip_with_decode_spo2(self):
        """Verify that files written by build_spo2_binary are 100% decoded by decode_spo2.py."""
        data = build_spo2_binary(self.sample_records, start_dt=self.start_dt)

        meta = parse_header(data)
        self.assertEqual(meta["magic"], "0x00000358")
        self.assertEqual(meta["version"], 1)
        self.assertEqual(meta["start_time"], self.start_dt)
        self.assertEqual(meta["sample_count"], 4)

        decoded_samples = parse_samples(data, meta["start_time"], header_count=meta["sample_count"])
        self.assertEqual(len(decoded_samples), 4)

        # Sample 1
        self.assertEqual(decoded_samples[0]["spo2"], 98)
        self.assertEqual(decoded_samples[0]["heart_rate"], 72)
        self.assertEqual(decoded_samples[0]["status"], "ok")

        # Sample 2
        self.assertEqual(decoded_samples[1]["spo2"], 97)
        self.assertEqual(decoded_samples[1]["heart_rate"], 71)
        self.assertEqual(decoded_samples[1]["status"], "ok")

        # Sample 3 (probe-out)
        self.assertIsNone(decoded_samples[2]["spo2"])
        self.assertIsNone(decoded_samples[2]["heart_rate"])
        self.assertEqual(decoded_samples[2]["status"], "probe-out")

        # Sample 4
        self.assertEqual(decoded_samples[3]["spo2"], 99)
        self.assertEqual(decoded_samples[3]["heart_rate"], 75)
        self.assertEqual(decoded_samples[3]["status"], "ok")

    def test_export_records_dispatch_spo2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "test.spo2")
            saved_path = export_records(self.sample_records, output_filename=out_file, fmt="spo2")
            self.assertEqual(saved_path, os.path.abspath(out_file))
            self.assertTrue(os.path.exists(saved_path))
            self.assertEqual(os.path.getsize(saved_path), SPO2_HEADER_SIZE + 4 * 2)

    def test_export_records_dispatch_auto_detect_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_spo2 = os.path.join(tmpdir, "my_session.spo2")
            saved_spo2 = export_records(self.sample_records, output_filename=out_spo2, fmt="csv")
            self.assertEqual(os.path.getsize(saved_spo2), SPO2_HEADER_SIZE + 4 * 2)

            out_csv = os.path.join(tmpdir, "my_session.csv")
            saved_csv = export_records(self.sample_records, output_filename=out_csv, fmt="spo2")
            with open(saved_csv, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertTrue(content.startswith("session_id,user_id"))

            out_json = os.path.join(tmpdir, "my_session.json")
            saved_json = export_records(self.sample_records, output_filename=out_json, fmt="spo2")
            with open(saved_json, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertTrue(content.strip().startswith("["))

    def test_export_records_default_filename(self):
        saved_path = export_records(self.sample_records, output_filename=None, fmt="spo2")
        try:
            self.assertTrue(os.path.exists(saved_path))
            self.assertTrue(os.path.basename(saved_path).startswith("fiedle400_all_sessions_"))
            self.assertTrue(saved_path.endswith(".spo2"))
        finally:
            if os.path.exists(saved_path):
                os.remove(saved_path)

    def test_export_records_unsupported_format(self):
        with self.assertRaises(ValueError):
            export_records(self.sample_records, output_filename="test.xml", fmt="xml")



class TestMultiSessionGap(unittest.TestCase):
    """T-020: the pause between two stored sessions must not be squeezed out of the file."""

    def _rec(self, ts, spo2=97):
        return {"timestamp": ts, "spo2": spo2, "heart_rate": 70, "flags": "ok"}

    def test_gap_between_sessions_is_padded_with_probe_out(self):
        # Real numbers from T-020: session 1 ends 08:40:11, session 2 starts 08:43:12 (181 s later).
        recs = [self._rec("2026-10-16T08:37:31"), self._rec("2026-10-16T08:37:32"),
                self._rec("2026-10-16T08:43:12"), self._rec("2026-10-16T08:43:13")]
        data = build_spo2_binary(recs)
        meta = parse_header(data)
        self.assertEqual(meta["start_time"], datetime(2026, 10, 16, 8, 37, 31))
        # 08:37:31 .. 08:43:13 inclusive = 343 s, not 4.
        self.assertEqual(meta["sample_count"], 343)
        samples = parse_samples(data, meta["start_time"], header_count=meta["sample_count"])
        self.assertEqual(len(samples), 343)
        self.assertEqual(samples[1]["spo2"], 97)
        self.assertEqual(samples[2]["status"], "probe-out")
        self.assertEqual(samples[340]["status"], "probe-out")
        self.assertEqual(samples[341]["spo2"], 97)   # 08:43:12 at its real time
        self.assertEqual(samples[342]["spo2"], 97)

    def test_continuous_session_is_unchanged(self):
        recs = [self._rec("2026-10-16T08:37:%02d" % s) for s in range(31, 41)]
        data = build_spo2_binary(recs)
        self.assertEqual(parse_header(data)["sample_count"], 10)

    def test_repeated_or_missing_timestamps_follow_one_second_apart(self):
        recs = [self._rec("2026-10-16T08:37:31"), self._rec("2026-10-16T08:37:31"),
                {"spo2": 96, "heart_rate": 70}, self._rec("garbage")]
        data = build_spo2_binary(recs)
        self.assertEqual(parse_header(data)["sample_count"], 4)

    def test_gap_over_twelve_hours_warns_and_is_not_padded(self):
        recs = [self._rec("2026-10-16T08:37:31"), self._rec("2026-10-17T20:37:31"),
                self._rec("2026-10-17T20:37:32")]
        with self.assertWarns(UserWarning):
            data = build_spo2_binary(recs)
        meta = parse_header(data)
        # records 1, one probe-out second marking the break, records 2 and 3
        self.assertEqual(meta["sample_count"], 4)
        samples = parse_samples(data, meta["start_time"], header_count=4)
        self.assertEqual(samples[1]["status"], "probe-out")
        self.assertEqual(samples[2]["spo2"], 97)

    def test_gap_just_under_twelve_hours_is_padded(self):
        recs = [self._rec("2026-10-16T08:00:00"), self._rec("2026-10-16T19:59:59")]
        data = build_spo2_binary(recs)
        self.assertEqual(parse_header(data)["sample_count"], 12 * 3600)

    def test_empty_records(self):
        self.assertEqual(parse_header(build_spo2_binary([]))["sample_count"], 0)


class TestPadRecords(unittest.TestCase):
    """T-022: callers that read records by list index need index == second."""

    def _rec(self, ts, v=97):
        return {"timestamp": ts, "spo2": v, "heart_rate": 70, "flags": "ok"}

    def test_gap_becomes_probe_out_records_with_real_timestamps(self):
        recs = [self._rec("2026-10-16T08:00:00"), self._rec("2026-10-16T08:00:04")]
        out = pad_records(recs)
        self.assertEqual(len(out), 5)
        self.assertEqual([r["flags"] for r in out], ["ok", "probe-out", "probe-out", "probe-out", "ok"])
        self.assertEqual(out[2]["timestamp"], "2026-10-16T08:00:02")
        self.assertIsNone(out[2]["spo2"])
        self.assertIs(out[4], recs[1])

    def test_continuous_records_come_back_unchanged(self):
        recs = [self._rec("2026-10-16T08:00:%02d" % i) for i in range(5)]
        self.assertEqual(pad_records(recs), recs)
        self.assertEqual(pad_records([]), [])

class TestExportHtml(unittest.TestCase):
    def test_html_format_writes_viewer_page_with_the_records(self):
        recs = [{"timestamp": "2026-10-16T08:00:00", "spo2": 97, "heart_rate": 70, "flags": "ok"}]
        with tempfile.TemporaryDirectory() as d:
            path = export_records(recs, fmt="html", output_dir=d)
            self.assertTrue(path.endswith(".html"))
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn('id="spo2-data"', html)
            self.assertIn("2026-10-16T08:00:00", html)
            # the extension also picks the format
            path2 = export_records(recs, os.path.join(d, "x.html"), fmt="csv")
            with open(path2, encoding="utf-8") as f:
                self.assertIn('id="spo2-data"', f.read())


if __name__ == "__main__":
    unittest.main()
