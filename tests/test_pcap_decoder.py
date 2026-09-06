import unittest
import os
import sys

# Ensure po400 and capture module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from capture.decode_pcap import parse_pcap_file, decode_pcap_reports
    HAS_CAPTURE_MODULE = True
except ImportError:
    HAS_CAPTURE_MODULE = False


class TestPcapDecoder(unittest.TestCase):

    def test_decode_raw_pcap_stream(self):
        if not HAS_CAPTURE_MODULE:
            self.skipTest("Legacy capture module not installed")
        pcap_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analysis", "bum400_20260906_100516.pcap"))
        if not os.path.exists(pcap_path):
            self.skipTest(f"PCAP file not found: {pcap_path}")

        reports = parse_pcap_file(pcap_path)
        self.assertGreater(len(reports), 0)

        sessions, samples = decode_pcap_reports(reports)
        self.assertEqual(len(sessions), 2)
        self.assertGreater(len(samples), 0)

        # Check that valid samples (status == ok) have physiological SpO2 (30..100) and HR (25..250)
        valid_samples = [s for s in samples if s["status"] == "ok"]
        self.assertGreater(len(valid_samples), 0)
        for s in valid_samples:
            self.assertTrue(30 <= s["spo2"] <= 100)
            self.assertTrue(25 <= s["heart_rate"] <= 250)


if __name__ == "__main__":
    unittest.main()
