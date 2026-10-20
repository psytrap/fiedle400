"""scripts/check_spo2_assistant_report.py (T-036): reads a SpO2 Assistant report XML and
compares it with a probe's expected.json. The XML here is built from the program's own format
strings (SPO2_ASSISTANT_CHECKS.md); no real report is involved."""

import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_spo2_assistant_report as check  # noqa: E402

EXPECTED = {"summary": {
    "total_event": 7, "index_per_hr": 9.65, "adjusted_index_per_hr": 9.66, "avg_low_spo2": 88.71,
    "min_spo2": 72, "time_below_88_s": 172, "basal_spo2_mean": 95.39,
    "total_event_with_other_params": {"drop=3": 8, "min_time=8": 9},
}}


def report(totle=7, index="9.7", drop=4, min_time=10):
    return (
        '<?xml version="1.0" encoding="utf-8"?><diagnosis><title></title><content>x</content>'
        f"<analy_result><event><totle><spo2>{totle}</spo2><pulse>0</pulse></totle>"
        "<time><spo2>6.2</spo2><pulse>0.0</pulse></time><avg><spo2>53.3</spo2><pulse></pulse></avg>"
        f"<index><spo2>{index}</spo2><pulse>0.0</pulse></index>"
        "<artifact><spo2>0.0</spo2><pulse>0.0</pulse></artifact>"
        "<artifact_index><spo2>9.7</spo2><pulse></pulse></artifact_index></event>"
        "<spo2><basal>96.2</basal><time_low>2.9</time_low><event_low>2</event_low><min>72</min>"
        "<event_min_avg>88.7</event_min_avg><event_min_avg_low>79.5</event_min_avg_low></spo2>"
        "<pulse><avg>70.0</avg><min>70</min></pulse></analy_result>"
        f"<analy_para><spo2><drop>{drop}</drop><min_time>{min_time}</min_time><max_time>180</max_time>"
        "<oscillation>1</oscillation><max_avg>2</max_avg><criteria>88</criteria></spo2>"
        "<pulse><drop>6</drop><time>8</time></pulse></analy_para></diagnosis>"
    )


class TestCheckReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.expected = os.path.join(self.tmp.name, "expected.json")
        with open(self.expected, "w") as f:
            json.dump(EXPECTED, f)

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, xml, *extra, encoding="utf-8"):
        path = os.path.join(self.tmp.name, "report.xml")
        with open(path, "w", encoding=encoding) as f:
            f.write(xml)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = check.main([path, self.expected, *extra])
        return rc, out.getvalue()

    def test_matching_report_at_printed_precision(self):
        rc, out = self.run_check(report())
        self.assertEqual(rc, 0, out)
        self.assertIn("| total_event (event/totle/spo2) | 7 | 7.0 | Match |", out)
        self.assertIn("time_below_88_s (spo2/time_low) | 2.9 | 2.9 | Match", out)
        self.assertNotIn("basal_spo2_mean", out)  # a superseded prediction is not compared

    def test_difference_is_reported(self):
        rc, out = self.run_check(report(totle=6))
        self.assertEqual(rc, 1)
        self.assertIn("**Differs**", out)

    def test_variant_checks_parameters_and_count(self):
        rc, out = self.run_check(report(totle=8, drop=3), "--variant", "drop=3")
        self.assertEqual(rc, 0, out)
        # The same report does not pass as the default run: its drop is 3.
        rc, out = self.run_check(report(totle=8, drop=3))
        self.assertEqual(rc, 1)
        self.assertIn("parameter spo2/drop | 4 | 3 | **Differs**", out)

    def test_utf16_file(self):
        rc, out = self.run_check(report(), encoding="utf-16")
        self.assertEqual(rc, 0, out)

    def test_not_a_report(self):
        with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()):
            rc, _ = self.run_check("<html></html>")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
