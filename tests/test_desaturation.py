"""Desaturation events and report values (T-018), checked against what the real
SpO2 Assistant reported for the T-019 probe recording (scripts/make_desat_probe.py)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fiedle400 import desaturation  # noqa: E402
import make_desat_probe  # noqa: E402
import make_pulse_basal_probe  # noqa: E402

# Flat, in-range baseline readings a test descent starts from and recovers back to --
# any steady in-range value works here, these just match what SpO2 Assistant's own
# probe used (T-019).
BASELINE_SPO2 = 97
BASELINE_PULSE = 70

# Samples of steady baseline bookending a test descent -- long enough that the
# descent itself, not the padding, is what the detector's state machine sees first/last.
FLAT_LEAD = 20
FLAT_TAIL = 10


def _fall(start, depth, dur):
    return [start - -(-depth * k // dur) for k in range(1, dur + 1)]


def _rise(start, depth, dur):
    """The climb back up from `start` to `start + depth` over `dur` samples -- the mirror
    of `_fall`, used for the recovery right after a descent."""
    return [start + -(-depth * k // dur) for k in range(1, dur + 1)]


def _padded(baseline, middle, lead=FLAT_LEAD, tail=FLAT_TAIL):
    """Flat baseline on both sides of `middle` -- every fixture below is just this plus
    some descent shape in the middle, so the detector's state machine sees the descent
    starting and ending mid-series, not at the very first/last sample."""
    return [baseline] * lead + middle + [baseline] * tail


def _descent_with_recovery(baseline, depth, duration, lead=FLAT_LEAD, tail=FLAT_TAIL):
    """A single plain descent (fall, then climb straight back to baseline one point per
    percent) -- the "just one clean event" fixture shared by tests that only need *an*
    event to detect/measure, not a specific shape."""
    nadir = baseline - depth
    middle = _fall(baseline, depth, duration) + _rise(nadir, depth, depth)
    return _padded(baseline, middle, lead, tail)


def _descent_broken_by_gap(baseline, first_depth, first_dur, gap, resume_value, second_depth, second_dur,
                            lead=FLAT_LEAD, tail=FLAT_TAIL):
    """A partial descent cut short by one invalid/probe-out sample (`gap`), then a second,
    separate partial descent starting from `resume_value` -- used to check that the gap
    stops the two partial descents being read as one continuous (and so accepted) event."""
    middle = _fall(baseline, first_depth, first_dur) + [gap, resume_value] + _fall(resume_value, second_depth, second_dur)
    return _padded(baseline, middle, lead, tail)


class TestDetectEvents(unittest.TestCase):
    def test_plain_event(self):
        depth, duration = desaturation.DROP, desaturation.MIN_TIME + 2  # comfortably inside every limit
        x = _descent_with_recovery(BASELINE_SPO2, depth, duration)
        ev = desaturation.detect_events(x)
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["from_pct"], ev[0]["to_pct"]), (BASELINE_SPO2, BASELINE_SPO2 - depth))
        self.assertEqual(ev[0]["nadir"] - ev[0]["start"], duration)

    def test_too_shallow(self):
        depth = desaturation.DROP - 1  # one below the accept threshold
        x = _padded(BASELINE_SPO2, _fall(BASELINE_SPO2, depth, 12))
        self.assertEqual(desaturation.detect_events(x), [])

    def test_too_short(self):
        duration = desaturation.MIN_TIME - 2  # below the minimum event duration
        x = _padded(BASELINE_SPO2, _fall(BASELINE_SPO2, desaturation.DROP, duration))
        self.assertEqual(desaturation.detect_events(x), [])

    def test_too_steep(self):
        duration = 12
        depth = desaturation.MAX_AVG * duration + 1  # average fall just over the allowed rate
        x = _padded(BASELINE_SPO2, _fall(BASELINE_SPO2, depth, duration))
        self.assertEqual(desaturation.detect_events(x), [])

    def test_probe_out_sample_breaks_an_event(self):
        # The second partial descent is too shallow/short on its own to be its own
        # event, so this only passes if the gap actually prevented the two from
        # being read as one continuous (and so accepted) descent.
        x = _descent_broken_by_gap(BASELINE_SPO2, 2, 6, desaturation.INVALID, 95, 3, 6)
        self.assertEqual(desaturation.detect_events(x), [])

    def test_none_counts_as_probe_out(self):
        x = _descent_broken_by_gap(BASELINE_SPO2, 2, 6, None, 95, 3, 6)
        self.assertEqual(desaturation.detect_events(x), [])

    def test_empty_and_flat(self):
        self.assertEqual(desaturation.detect_events([]), [])
        self.assertEqual(desaturation.detect_events([BASELINE_SPO2] * 100), [])


class TestAgainstSpo2AssistantProbe(unittest.TestCase):
    """Numbers below are what the real program reported (T-019, 2026-10-20) -- golden
    values from the real SpO2 Assistant run, not thresholds of this module's own, so
    they are left as literals rather than expressed via desaturation.py's constants."""

    @classmethod
    def setUpClass(cls):
        cls.series, cls.cases = make_desat_probe.build_series()
        cls.events = desaturation.detect_events(cls.series)
        cls.summary = desaturation.summarize(cls.series, cls.events)

    def test_event_count_for_default_and_changed_parameters(self):
        self.assertEqual(len(self.events), 7)
        self.assertEqual(len(desaturation.detect_events(self.series, drop=3)), 8)
        self.assertEqual(len(desaturation.detect_events(self.series, min_time=8)), 9)

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
        self.assertEqual(desaturation.summarize([], [])["total_event"], 0)

    def test_no_events_gives_none_for_event_averages(self):
        s = desaturation.summarize([BASELINE_SPO2] * 60, [])
        self.assertIsNone(s["avg_low_spo2"])
        self.assertEqual(s["basal_spo2"], float(BASELINE_SPO2))

    def test_all_invalid(self):
        s = desaturation.summarize([None] * 30, [])
        self.assertIsNone(s["basal_spo2"])
        self.assertEqual(s["artifact_pct"], 100.0)

    def test_time_below_criteria_uses_the_same_valid_samples_as_artifact_pct(self):
        # T-044: a raw 0 is neither a valid reading nor a null probe-out gap -- it must
        # be excluded from both artifact_pct and time_below_criteria_s the same way, not
        # just from one of them (the mismatch the viewer's own separate counts had).
        above_count, below_count, zero_count, none_count = 10, 5, 3, 2
        below_value = desaturation.CRITERIA - 3  # comfortably under criteria, still a valid reading

        x = [BASELINE_SPO2] * above_count + [below_value] * below_count + [0] * zero_count + [None] * none_count
        s = desaturation.summarize(x, [])  # default criteria

        total, invalid = len(x), zero_count + none_count
        self.assertEqual(s["valid_samples"], above_count + below_count)  # excludes the 0s and the Nones
        self.assertEqual(s["artifact_pct"], round(100.0 * invalid / total, 2))
        self.assertEqual(s["time_below_criteria_s"], below_count)  # the below_value samples, not the 0s


class TestBasalSpo2(unittest.TestCase):
    """The rule decoded from SpO2.exe (T-031): mean of the valid samples outside every
    event's start..nadir, with no fallback when nothing is left."""

    def test_event_descent_is_left_out_but_the_recovery_is_not(self):
        depth, duration = desaturation.DROP, desaturation.MIN_TIME + 2
        x = _descent_with_recovery(BASELINE_SPO2, depth, duration)
        ev = desaturation.detect_events(x)
        s = desaturation.summarize(x, ev)
        outside = [v for i, v in enumerate(x) if not ev[0]["start"] <= i <= ev[0]["nadir"]]
        self.assertAlmostEqual(s["basal_spo2"], round(sum(outside) / len(outside), 2))

    def test_low_samples_outside_events_count(self):
        # A fall to 85 % held so long that the flat part makes it longer than MAX_TIME:
        # no event, so all of it counts.
        x = [BASELINE_SPO2] * 60 + _fall(BASELINE_SPO2, 12, 6) + [85] * (desaturation.MAX_TIME + 20)
        self.assertEqual(desaturation.detect_events(x), [])
        self.assertAlmostEqual(desaturation.summarize(x, [])["basal_spo2"], round(sum(x) / len(x), 2))

    def test_nothing_outside_events_gives_none(self):
        x = [None, BASELINE_SPO2] + _fall(BASELINE_SPO2, 5, 12)
        ev = desaturation.detect_events(x)
        self.assertEqual(len(ev), 1)
        self.assertIsNone(desaturation.summarize(x, ev)["basal_spo2"])


class TestPulseEvents(unittest.TestCase):
    """The pulse-rate detector is the SpO2 one with desaturation.PULSE_DROP/PULSE_MIN_TIME
    and range 0..254 (T-029)."""

    def test_a_fall_is_an_event_and_a_rise_is_not(self):
        fall = _padded(BASELINE_PULSE, _fall(BASELINE_PULSE, desaturation.PULSE_DROP, 10))
        self.assertEqual(len(desaturation.detect_pulse_events(fall)), 1)
        # Not _padded: the tail is a different plateau, not back at baseline -- a rise
        # settling somewhere new must still not be an event (the detector only looks for falls).
        new_plateau, climb_duration, tail_len = 80, 10, 20
        rise = [BASELINE_PULSE] * FLAT_LEAD + _rise(BASELINE_PULSE, new_plateau - BASELINE_PULSE, climb_duration) + [new_plateau] * tail_len
        self.assertEqual(desaturation.detect_pulse_events(rise), [])

    def test_defaults_and_values_above_100(self):
        baseline = 140  # above the SpO2 channel's 0..100 range -- the pulse detector allows up to 254
        duration = desaturation.PULSE_MIN_TIME  # exactly at the minimum accepted duration
        x = _padded(baseline, _fall(baseline, desaturation.PULSE_DROP, duration))
        self.assertEqual(len(desaturation.detect_pulse_events(x)), 1)
        self.assertEqual(desaturation.detect_pulse_events(x, min_time=duration + 1), [])

        too_shallow = desaturation.PULSE_DROP - 1
        shallow_fall = [BASELINE_PULSE] * FLAT_LEAD + _fall(BASELINE_PULSE, too_shallow, 10)
        self.assertEqual(desaturation.detect_pulse_events(shallow_fall), [])
        self.assertEqual(len(desaturation.detect_pulse_events(shallow_fall, drop=too_shallow)), 1)

    def test_probe_out_breaks_a_pulse_event(self):
        # Same gap-breaks-a-descent check as the SpO2 channel's test_probe_out_sample_breaks_an_event:
        # each partial descent (depth/duration below) is too shallow/short to be its own event, so
        # this only passes if the gap actually prevented them being read as one continuous descent.
        first_depth, first_dur = 3, 5
        resume_value = 67  # arbitrary lower value the series resumes at right after the gap
        second_depth, second_dur = 4, 5
        for gap in (None, desaturation.PULSE_INVALID):
            x = _descent_broken_by_gap(BASELINE_PULSE, first_depth, first_dur, gap, resume_value, second_depth, second_dur)
            self.assertEqual(desaturation.detect_pulse_events(x), [], gap)


class TestSummarizePulse(unittest.TestCase):
    """Pulse report values (SPO2_FORMAT.md §7.1): same formulas as the SpO2 channel."""

    def test_values(self):
        # Plenty of valid baseline samples either side of the one event, so index_per_hr
        # and artifact_pct below have enough of a denominator to not be a degenerate case.
        valid_lead, valid_tail = 1000, 1000
        event_duration = 10  # arbitrary, comfortably above PULSE_MIN_TIME

        # None, a raw 0 and the probe-out sentinel are each invalid for a different reason;
        # a different count per kind confirms they're all being excluded, not just one.
        none_count, zero_count, sentinel_count = 50, 50, 100

        core = _padded(BASELINE_PULSE, _fall(BASELINE_PULSE, desaturation.PULSE_DROP, event_duration),
                       lead=valid_lead, tail=valid_tail)
        x = core + [None] * none_count + [0] * zero_count + [desaturation.PULSE_INVALID] * sentinel_count
        ev = desaturation.detect_pulse_events(x)
        self.assertEqual(len(ev), 1)
        s = desaturation.summarize_pulse(x, ev)
        n, bad = len(x), none_count + zero_count + sentinel_count
        self.assertEqual((s["samples"], s["valid_samples"], s["total_event"]), (n, n - bad, 1))
        self.assertEqual(s["index_per_hr"], round(3600.0 / n, 2))
        self.assertEqual(s["adjusted_index_per_hr"], round(3600.0 / (n - bad), 2))
        self.assertEqual(s["artifact_pct"], round(100.0 * bad / n, 2))
        self.assertEqual(s["avg_event_duration_s"], float(event_duration))

    def test_no_events_and_empty(self):
        s = desaturation.summarize_pulse([BASELINE_PULSE] * 100, [])
        self.assertEqual((s["total_event"], s["index_per_hr"], s["avg_event_duration_s"]), (0, 0.0, None))
        self.assertEqual(desaturation.summarize_pulse([], []), dict(samples=0, valid_samples=0, total_event=0))
        self.assertIsNone(desaturation.summarize_pulse([None] * 5, [])["adjusted_index_per_hr"])


class TestValidIndices(unittest.TestCase):
    """desaturation._valid_indices: the shared valid-sample filter behind both summarize
    functions (None and out-of-[lo, hi] values are excluded, same as artifact_pct)."""

    def test_excludes_none_and_out_of_range(self):
        self.assertEqual(desaturation._valid_indices([97, None, 0, 101, 50], 1, 100), [0, 4])

    def test_bounds_are_inclusive(self):
        self.assertEqual(desaturation._valid_indices([1, 100], 1, 100), [0, 1])

    def test_empty_series(self):
        self.assertEqual(desaturation._valid_indices([], 1, 100), [])


class TestAvgEventDuration(unittest.TestCase):
    """desaturation._avg_event_duration: shared by summarize/summarize_pulse's
    avg_event_duration_s field."""

    def test_no_events_is_none(self):
        self.assertIsNone(desaturation._avg_event_duration([]))

    def test_mean_of_nadir_minus_start(self):
        events = [dict(start=0, nadir=10), dict(start=5, nadir=25)]
        self.assertEqual(desaturation._avg_event_duration(events), 15.0)


class TestEventRateStats(unittest.TestCase):
    """desaturation._event_rate_stats: the index_per_hr/adjusted_index_per_hr/artifact_pct
    trio shared by summarize and summarize_pulse."""

    def test_rates_scale_with_sample_count(self):
        stats = desaturation._event_rate_stats(total_samples=3600, valid_count=3600, event_count=2)
        self.assertEqual(stats["index_per_hr"], 2.0)
        self.assertEqual(stats["adjusted_index_per_hr"], 2.0)
        self.assertEqual(stats["artifact_pct"], 0.0)

    def test_artifact_pct_reflects_invalid_share(self):
        stats = desaturation._event_rate_stats(total_samples=100, valid_count=75, event_count=0)
        self.assertEqual(stats["artifact_pct"], 25.0)

    def test_adjusted_index_is_none_with_no_valid_samples(self):
        stats = desaturation._event_rate_stats(total_samples=100, valid_count=0, event_count=1)
        self.assertIsNone(stats["adjusted_index_per_hr"])


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
