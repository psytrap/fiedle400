"""Unit tests for PO-400 oximetry plotting tool."""

import os
import tempfile
import unittest
from datetime import datetime

from po400.export import build_spo2_binary

try:
    from po400.plot import (
        load_session_file,
        plot_session,
        find_latest_session_file,
    )
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@unittest.skipUnless(HAS_MATPLOTLIB, "matplotlib not installed (optional 'plot' extra)")
class TestPlot(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.start_dt = datetime(2026, 9, 30, 20, 0, 0)
        self.records = [
            {"timestamp": "2026-09-30T20:00:00", "spo2": 98, "heart_rate": 70},
            {"timestamp": "2026-09-30T20:00:01", "spo2": 97, "heart_rate": 72},
            {"timestamp": "2026-09-30T20:00:02", "spo2": None, "heart_rate": None},
            {"timestamp": "2026-09-30T20:00:03", "spo2": 96, "heart_rate": 75},
        ]
        # Create a sample .spo2 file
        self.spo2_path = os.path.join(self.tmpdir.name, "test_session.spo2")
        bin_data = build_spo2_binary(self.records, start_dt=self.start_dt)
        with open(self.spo2_path, "wb") as f:
            f.write(bin_data)

        # Create a sample .csv file
        self.csv_path = os.path.join(self.tmpdir.name, "test_session.csv")
        with open(self.csv_path, "w", encoding="utf-8") as f:
            f.write("timestamp,spo2,heart_rate\n")
            f.write("2026-09-30T20:00:00,98,70\n")
            f.write("2026-09-30T20:00:01,97,72\n")
            f.write("2026-09-30T20:00:02,,\n")
            f.write("2026-09-30T20:00:03,96,75\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_spo2_file(self):
        dt, recs = load_session_file(self.spo2_path)
        self.assertEqual(dt, self.start_dt)
        self.assertEqual(len(recs), 4)
        self.assertEqual(recs[0]["spo2"], 98)
        self.assertEqual(recs[0]["heart_rate"], 70)
        self.assertTrue(recs[2]["spo2"] != recs[2]["spo2"])  # NaN

    def test_load_csv_file(self):
        dt, recs = load_session_file(self.csv_path)
        self.assertEqual(dt, self.start_dt)
        self.assertEqual(len(recs), 4)
        self.assertEqual(recs[0]["spo2"], 98)
        self.assertEqual(recs[1]["heart_rate"], 72)

    def test_plot_session_generates_valid_png(self):
        png_out = os.path.join(self.tmpdir.name, "test_chart.png")
        saved_path = plot_session(filepath=self.spo2_path, output_png=png_out, dpi=100)
        self.assertEqual(saved_path, os.path.abspath(png_out))
        self.assertTrue(os.path.exists(saved_path))
        self.assertGreater(os.path.getsize(saved_path), 1000)

        # Verify PNG header magic signature (\x89PNG\r\n\x1a\n)
        with open(saved_path, "rb") as f:
            header = f.read(8)
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")

    def test_plot_session_csv_input(self):
        png_out = os.path.join(self.tmpdir.name, "from_csv.png")
        saved_path = plot_session(filepath=self.csv_path, output_png=png_out, dpi=100)
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, "rb") as f:
            header = f.read(8)
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")

    def test_find_latest_session_file(self):
        latest = find_latest_session_file(self.tmpdir.name)
        self.assertIsNotNone(latest)
        self.assertTrue(latest.endswith((".spo2", ".csv")))


if __name__ == "__main__":
    unittest.main()
