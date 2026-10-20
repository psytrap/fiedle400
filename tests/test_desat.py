"""Desaturation events and report values (T-018), checked against what the real
SpO2 Assistant reported for the T-019 probe recording (scripts/make_desat_probe.py)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fiedle400 import desat  # noqa: E402
import make_desat_probe  # noqa: E402


def _fall(start, depth, dur):
    return [start - -(-depth * k // dur) for k in range(1, dur + 1)]


class TestDetectEvents(unittest.TestCase):
    def test_plain_event(self):
        x = [97] * 20 + _fall(97, 4, 12) + [94, 95, 96, 97] + [97] * 10
        ev = desat.detect_events(x)
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["from_pct"], ev[0]["to_pct"]), (97, 93))
        self.assertEqual(ev[0]["nadir"] - ev[0]["start"], 12)

    def test_too_shallow_too_short_too_steep(self):
        self.assertEqual(desat.detect_events([97] * 20 + _fall(97, 3, 12) + [97] * 10), [])
        self.assertEqual(desat.detect_events([97] * 20 + _fall(97, 4, 8) + [97] * 10), [])
        self.assertEqual(desat.detect_events([97] * 20 + _fall(97, 25, 12) + [97] * 10), [])

    def test_probe_out_sample_breaks_an_event(self):
        x = [97] * 20 + _fall(97, 2, 6) + [127, 95] + _fall(95, 3, 6) + [97] * 10
        self.assertEqual(desat.detect_events(x), [])

    def test_none_counts_as_probe_out(self):
        x = [97] * 20 + _fall(97, 2, 6) + [None, 95] + _fall(95, 3, 6) + [97] * 10
        self.assertEqual(desat.detect_events(x), [])

    def test_empty_and_flat(self):
        self.assertEqual(desat.detect_events([]), [])
        self.assertEqual(desat.detect_events([97] * 100), [])


class TestAgainstSpo2AssistantProbe(unittest.TestCase):
    """Numbers below are what the real program reported (T-019, 2026-10-20)."""

    @classmethod
    def setUpClass(cls):
        cls.series, cls.cases = make_desat_probe.build_series()
        cls.events = desat.detect_events(cls.series)
        cls.summary = desat.summarize(cls.series, cls.events)

    def test_event_count_for_default_and_changed_parameters(self):
        self.assertEqual(len(self.events), 7)
        self.assertEqual(len(desat.detect_events(self.series, drop=3)), 8)
        self.assertEqual(len(desat.detect_events(self.series, min_time=8)), 9)

    def test_events_sit_in_the_cases_expected_to_have_one(self):
        for c in self.cases:
            got = [e for e in self.events if c["start_s"] - 1 <= e["start"] < c["end_s"]]
            self.assertEqual("event" if got else "none", c["expect"], c["name"])

    def test_report_values(self):
        s = self.summary
        self.assertEqual(s["total_event"], 7)
        self.assertAlmostEqual(s["index_per_hr"], 9.65, places=2)
        self.assertAlmostEqual(s["avg_low_spo2"], 88.71, places=2)
        self.assertEqual(s["events_below_criteria"], 2)
        self.assertAlmostEqual(s["avg_low_spo2_below_criteria"], 79.5, places=2)
        self.assertAlmostEqual(s["avg_event_duration_s"], 53.3, places=1)

    def test_basal_spo2_matches_the_program_to_its_printed_precision(self):
        # SpO2 Assistant printed 96.2 (the plain mean of valid samples is 95.39).
        self.assertEqual(round(self.summary["basal_spo2"], 1), 96.2)


class TestSummarizeEdgeCases(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(desat.summarize([], [])["total_event"], 0)

    def test_no_events_gives_none_for_event_averages(self):
        s = desat.summarize([97] * 60, [])
        self.assertIsNone(s["avg_low_spo2"])
        self.assertEqual(s["basal_spo2"], 97.0)

    def test_all_invalid(self):
        s = desat.summarize([None] * 30, [])
        self.assertIsNone(s["basal_spo2"])
        self.assertEqual(s["artifact_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
