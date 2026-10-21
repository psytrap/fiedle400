"""Regression test: decode the reference USB capture in analysis/ end to end."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))
from decode_pcap import parse_pcap_file, decode_pcap_reports

PCAP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analysis", "bum400_20260906_100516.pcap"))

# SpO2 Assistant's own download of the recording in bum400.pcapng (archive/ is not in git: the test
# runs where the capture is present, e.g. psytrap's checkout and the cloud mirror).
CAPTURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "archive", "capture"))
VENDOR_PCAP = os.path.join(CAPTURE_DIR, "bum400.pcapng")
VENDOR_FILE = os.path.join(CAPTURE_DIR, "_user_1_0_20260903074127-20260903074137joint.SpO2")


class TestPcapDecoder(unittest.TestCase):

    def test_decode_raw_pcap_stream(self):
        reports = parse_pcap_file(PCAP_PATH)
        self.assertGreater(len(reports), 0)

        sessions, samples = decode_pcap_reports(reports)
        # The capture holds a single 0xEC session header: session 1, 243 samples, one per
        # second (T-075; analysis/bum400_20260906_100516.md frame 067 read it as 2 Hz).
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], 1)
        self.assertEqual(sessions[0]["raw_samples"], 243)
        self.assertEqual(sessions[0]["record_count"], 243)
        self.assertGreater(len(samples), 0)

        # Check that valid samples (status == ok) have physiological SpO2 (30..100) and HR (25..250)
        valid_samples = [s for s in samples if s["status"] == "ok"]
        self.assertGreater(len(valid_samples), 0)
        for s in valid_samples:
            self.assertTrue(30 <= s["spo2"] <= 100)
            self.assertTrue(25 <= s["heart_rate"] <= 250)

    @unittest.skipUnless(os.path.exists(VENDOR_PCAP) and os.path.exists(VENDOR_FILE), "archive/capture not present")
    def test_one_value_per_second_like_spo2_assistants_own_file(self):
        """T-075: the vendor file has one record per header count, and the same SpO2 values."""
        from fiedle400.recording import read_spo2_file
        sessions, samples = decode_pcap_reports(parse_pcap_file(VENDOR_PCAP))
        self.assertEqual(sessions[0]["raw_samples"], 9705)
        _, vendor = read_spo2_file(VENDOR_FILE)
        ours = [s["spo2"] for s in samples if s.get("spo2")][:9705]
        self.assertEqual(ours, [r["spo2"] for r in vendor[:9705]])
        self.assertNotIn(vendor[9705]["spo2"], range(1, 101))  # the gap before session 2 starts here

    def test_legacy_pcap_little_endian_is_parsed(self):
        """A little-endian legacy pcap (d4 c3 b2 a1 on disk) must yield reports, not an empty list."""
        with open(PCAP_PATH, "rb") as f:
            self.assertEqual(f.read(4), b"\xd4\xc3\xb2\xa1")
        self.assertGreater(len(parse_pcap_file(PCAP_PATH)), 0)


if __name__ == "__main__":
    unittest.main()
