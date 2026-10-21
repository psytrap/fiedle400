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
import make_pulse_basal_probe  # noqa: E402


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

    def test_time_below_criteria_uses_the_same_valid_samples_as_artifact_pct(self):
        # T-044: a raw 0 is neither a valid reading nor a null probe-out gap -- it must
        # be excluded from both artifact_pct and time_below_criteria_s the same way, not
        # just from one of them (the mismatch the viewer's own separate counts had).
        x = [97] * 10 + [85] * 5 + [0] * 3 + [None] * 2
        s = desat.summarize(x, [], criteria=88)
        self.assertEqual(s["valid_samples"], 15)  # excludes the 0s and the Nones
        self.assertEqual(s["artifact_pct"], 25.0)  # 5 invalid / 20
        self.assertEqual(s["time_below_criteria_s"], 5)  # the five 85s, not the 0s


class TestBasalSpo2(unittest.TestCase):
    """The rule decoded from SpO2.exe (T-031): mean of the valid samples outside every
    event's start..nadir, with no fallback when nothing is left."""

    def test_event_descent_is_left_out_but_the_recovery_is_not(self):
        x = [97] * 20 + _fall(97, 4, 12) + [94, 95, 96, 97] + [97] * 10
        ev = desat.detect_events(x)
        s = desat.summarize(x, ev)
        outside = [v for i, v in enumerate(x) if not ev[0]["start"] <= i <= ev[0]["nadir"]]
        self.assertAlmostEqual(s["basal_spo2"], round(sum(outside) / len(outside), 2))

    def test_low_samples_outside_events_count(self):
        # A fall to 85 % held so long that the flat part makes it longer than 180 s:
        # no event, so all of it counts.
        x = [97] * 60 + _fall(97, 12, 6) + [85] * 200
        self.assertEqual(desat.detect_events(x), [])
        self.assertAlmostEqual(desat.summarize(x, [])["basal_spo2"], round(sum(x) / len(x), 2))

    def test_nothing_outside_events_gives_none(self):
        x = [None, 97] + _fall(97, 5, 12)
        ev = desat.detect_events(x)
        self.assertEqual(len(ev), 1)
        self.assertIsNone(desat.summarize(x, ev)["basal_spo2"])


class TestPulseEvents(unittest.TestCase):
    """The pulse-rate detector is the SpO2 one with 6 bpm / 8 s and range 0..254 (T-029)."""

    def test_a_fall_is_an_event_and_a_rise_is_not(self):
        self.assertEqual(len(desat.detect_pulse_events([70] * 20 + _fall(70, 6, 10) + [70] * 10)), 1)
        rise = [70] * 20 + [70 + k for k in range(1, 11)] + [80] * 20
        self.assertEqual(desat.detect_pulse_events(rise), [])

    def test_defaults_and_values_above_100(self):
        x = [140] * 20 + _fall(140, 6, 8) + [140] * 10
        self.assertEqual(len(desat.detect_pulse_events(x)), 1)
        self.assertEqual(desat.detect_pulse_events(x, min_time=9), [])
        self.assertEqual(desat.detect_pulse_events([70] * 20 + _fall(70, 5, 10)), [])
        self.assertEqual(len(desat.detect_pulse_events([70] * 20 + _fall(70, 5, 10), drop=5)), 1)

    def test_probe_out_breaks_a_pulse_event(self):
        for gap in (None, 255):
            x = [70] * 20 + _fall(70, 3, 5) + [gap, 67] + _fall(67, 4, 5) + [70] * 10
            self.assertEqual(desat.detect_pulse_events(x), [], gap)


class TestSummarizePulse(unittest.TestCase):
    """Pulse report values (SPO2_FORMAT.md §7.1): same formulas as the SpO2 channel."""

    def test_values(self):
        x = [70] * 1000 + _fall(70, 6, 10) + [70] * 1000 + [None] * 50 + [0] * 50 + [255] * 100
        ev = desat.detect_pulse_events(x)
        self.assertEqual(len(ev), 1)
        s = desat.summarize_pulse(x, ev)
        n, bad = len(x), 200  # None, 0 and 255 are not valid pulse values
        self.assertEqual((s["samples"], s["valid_samples"], s["total_event"]), (n, n - bad, 1))
        self.assertEqual(s["index_per_hr"], round(3600.0 / n, 2))
        self.assertEqual(s["adjusted_index_per_hr"], round(3600.0 / (n - bad), 2))
        self.assertEqual(s["artifact_pct"], round(100.0 * bad / n, 2))
        self.assertEqual(s["avg_event_duration_s"], 10.0)

    def test_no_events_and_empty(self):
        s = desat.summarize_pulse([70] * 100, [])
        self.assertEqual((s["total_event"], s["index_per_hr"], s["avg_event_duration_s"]), (0, 0.0, None))
        self.assertEqual(desat.summarize_pulse([], []), dict(samples=0, valid_samples=0, total_event=0))
        self.assertIsNone(desat.summarize_pulse([None] * 5, [])["adjusted_index_per_hr"])


class TestPulseBasalProbe(unittest.TestCase):
    """scripts/make_pulse_basal_probe.py: every case lands as designed, and the three
    Basal candidates differ at the program's printed precision (T-035 checks them)."""

    def test_cases_and_diverging_basal_rules(self):
        spo2, pulse, cases = make_pulse_basal_probe.build_series()
        summary = make_pulse_basal_probe.predict(spo2, pulse, cases)  # asserts each case
        self.assertEqual((summary["spo2_total_event"], summary["pulse_total_event"]), (2, 4))
        rules = {summary["basal_spo2_decoded"], summary["basal_spo2_if_plain_mean"],
                 summary["basal_spo2_if_mean_of_samples_at_or_above_88"]}
        self.assertEqual(len(rules), 3)


if __name__ == "__main__":
    unittest.main()
