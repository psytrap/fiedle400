"""Regression test: decode the reference USB capture in analysis/ end to end."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))
from decode_pcap import parse_pcap_file, decode_pcap_reports

PCAP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analysis", "bum400_20260906_100516.pcap"))


class TestPcapDecoder(unittest.TestCase):

    def test_decode_raw_pcap_stream(self):
        reports = parse_pcap_file(PCAP_PATH)
        self.assertGreater(len(reports), 0)

        sessions, samples = decode_pcap_reports(reports)
        # The capture holds a single 0xEC session header: session 1, 243 raw 2 Hz
        # samples = 122 one-second records (see analysis/bum400_20260906_100516.md, frame 067).
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], 1)
        self.assertEqual(sessions[0]["raw_samples"], 243)
        self.assertEqual(sessions[0]["record_count"], 122)
        self.assertGreater(len(samples), 0)

        # Check that valid samples (status == ok) have physiological SpO2 (30..100) and HR (25..250)
        valid_samples = [s for s in samples if s["status"] == "ok"]
        self.assertGreater(len(valid_samples), 0)
        for s in valid_samples:
            self.assertTrue(30 <= s["spo2"] <= 100)
            self.assertTrue(25 <= s["heart_rate"] <= 250)

    def test_legacy_pcap_little_endian_is_parsed(self):
        """A little-endian legacy pcap (d4 c3 b2 a1 on disk) must yield reports, not an empty list."""
        with open(PCAP_PATH, "rb") as f:
            self.assertEqual(f.read(4), b"\xd4\xc3\xb2\xa1")
        self.assertGreater(len(parse_pcap_file(PCAP_PATH)), 0)


if __name__ == "__main__":
    unittest.main()
