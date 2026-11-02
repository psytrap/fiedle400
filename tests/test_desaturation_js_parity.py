"""The viewer's JS detectEvents/summarizeEvents must give exactly what desaturation.py gives (T-027).

The JS is a hand-written port of desaturation.py that runs in the browser when the user changes
the parameters. This test extracts the marked block from the shipped page, runs it under
Node (no npm packages; skipped when `node` is not installed -- GitHub's runners have it)
and compares events and every summary value with the Python original for the cases of
tests/test_desaturation.py, the T-019 probe, parameter variants and a seeded random fuzz.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fiedle400 import desaturation, spo2_viewer  # noqa: E402
import make_desat_probe  # noqa: E402

BEGIN, END = "// BEGIN desaturation-port", "// END desaturation-port"

RUNNER = """
var fs = require('fs');
var block = process.argv[1];
var port = new Function(block + '; return {detectEvents: detectEvents, summarizeEvents: summarizeEvents, summarizePulse: summarizePulse, PULSE_HIGH: PULSE_HIGH, PULSE_INVALID: PULSE_INVALID};')();
var cases = JSON.parse(fs.readFileSync(0, 'utf8'));
var out = cases.map(function (c) {
  if (c.pulse) {
    var pe = port.detectEvents(c.spo2, c.drop, c.min_time, port.PULSE_HIGH, port.PULSE_INVALID);
    return {events: pe, summary: port.summarizePulse(c.spo2, pe)};
  }
  var events = port.detectEvents(c.spo2, c.drop, c.min_time);
  return {events: events, summary: port.summarizeEvents(c.spo2, events, c.criteria)};
});
process.stdout.write(JSON.stringify(out));
"""


def _js_block():
    html = spo2_viewer.build_viewer_html([{"timestamp": "2026-10-20T22:00:00", "spo2": 97, "heart_rate": 70, "flags": None}])
    begin_index, end_index = html.index(BEGIN), html.index(END)
    return html[html.index("\n", begin_index):end_index]  # from the line after BEGIN


def _fall(start, depth, duration):
    return [start - -(-depth * k // duration) for k in range(1, duration + 1)]


def _desaturation_cases():
    """The sequences of tests/test_desaturation.py."""
    return [
        [97] * 20 + _fall(97, 4, 12) + [94, 95, 96, 97] + [97] * 10,
        [97] * 20 + _fall(97, 3, 12) + [97] * 10,
        [97] * 20 + _fall(97, 4, 8) + [97] * 10,
        [97] * 20 + _fall(97, 25, 12) + [97] * 10,
        [97] * 20 + _fall(97, 2, 6) + [127, 95] + _fall(95, 3, 6) + [97] * 10,
        [97] * 20 + _fall(97, 2, 6) + [None, 95] + _fall(95, 3, 6) + [97] * 10,
        [],
        [97] * 100,
        [None] * 30,
        [97] * 60,
        [None] + [97 - k for k in range(13)],  # every valid sample inside one event
    ]


def _fuzz_cases(count, seed=400):
    generator = random.Random(seed)
    output = []
    for _ in range(count):
        length = generator.randint(30, 700)
        value = generator.randint(88, 99)
        series = []
        while len(series) < length:
            kind = generator.random()
            if kind < 0.35:  # plateau
                series += [value] * generator.randint(1, 25)
            elif kind < 0.65:  # staircase / slope down, possibly with small rebounds
                for _ in range(generator.randint(2, 30)):
                    value = max(60, value - generator.choice((0, 0, 1, 1, 1, 2)))
                    if generator.random() < 0.08:
                        value = min(100, value + 1)
                    series.append(value)
            elif kind < 0.85:  # recovery
                for _ in range(generator.randint(1, 15)):
                    value = min(100, value + generator.choice((0, 1, 1, 2)))
                    series.append(value)
            elif kind < 0.93:  # gap
                series += [generator.choice((None, 127, 0, 255))] * generator.randint(1, 6)
            else:  # noise
                value = max(60, min(100, value + generator.randint(-2, 2)))
                series.append(value)
        output.append(series[:length])
    return output


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestJsMatchesPython(unittest.TestCase):
    PARAMETERS = [(4, 10, 88), (3, 10, 88), (4, 8, 88), (3, 4, 90), (4, 10, 90), (5, 12, 85)]

    @classmethod
    def setUpClass(cls):
        cls.block = _js_block()

    def _run_js(self, cases):
        proc = subprocess.run(["node", "-e", RUNNER, self.block], input=json.dumps(cases),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def _compare(self, series_list, parameters):
        cases = [dict(spo2=case_series, drop=drop, min_time=min_time, criteria=criteria) for case_series in series_list for drop, min_time, criteria in parameters]
        got = self._run_js(cases)
        self.assertEqual(len(got), len(cases))
        for case, js_result in zip(cases, got):
            events = desaturation.detect_events(case["spo2"], drop=case["drop"], min_time=case["min_time"])
            python_result = json.loads(json.dumps({"events": events,
                                        "summary": desaturation.summarize(case["spo2"], events, case["criteria"])}))
            where = f"drop={case['drop']} min_time={case['min_time']} criteria={case['criteria']} spo2={case['spo2']}"
            self.assertEqual(js_result["events"], python_result["events"], where)
            self.assertEqual(js_result["summary"], python_result["summary"], where)

    def test_cases_of_the_python_tests(self):
        self._compare(_desaturation_cases(), self.PARAMETERS)

    def test_basal_is_not_computed_when_every_valid_sample_is_in_an_event(self):
        series = [None] + [97 - k for k in range(13)]
        self.assertEqual(len(desaturation.detect_events(series)), 1)
        got = self._run_js([dict(spo2=series, drop=4, min_time=10, criteria=88)])[0]
        self.assertIsNone(got["summary"]["basal_spo2"])
        self._compare([series], [(4, 10, 88)])

    def test_t019_probe_with_default_and_changed_parameters(self):
        series, _ = make_desat_probe.build_series()
        self._compare([series], self.PARAMETERS)
        # The numbers the real program reported (7 / 8 / 9 events) hold for the JS too.
        cases = [dict(spo2=series, drop=drop, min_time=min_time, criteria=88) for drop, min_time in ((4, 10), (3, 10), (4, 8))]
        self.assertEqual([len(result["events"]) for result in self._run_js(cases)], [7, 8, 9])

    def test_seeded_random_sequences(self):
        series = _fuzz_cases(300)
        found = sum(len(desaturation.detect_events(case_series)) for case_series in series)
        self.assertGreater(found, 50)  # the fuzz must actually produce events to compare
        self._compare(series, self.PARAMETERS[:4])

    def test_rounding_ties_follow_python(self):
        # Exact ties (x.25, x.125 ...) go to the even digit in Python's round(); Math.round does not.
        # Four events averaging 0.25 s steps: durations 10, 10, 10, 11 -> mean 10.25 -> 10.2.
        series = []
        for duration in (10, 10, 10, 11):
            series += [97] * 15 + _fall(97, 4, duration) + [96, 97]
        events = desaturation.detect_events(series)
        self.assertEqual(len(events), 4)
        self.assertEqual(desaturation.summarize(series, events)["average_event_duration_seconds"], 10.2)
        self._compare([series], [(4, 10, 88)])

    # Pulse series (T-030): same detector with range 0..254 / probe-out 255, plus summarize_pulse.
    PULSE_PARAMETERS = [(6, 8), (4, 8), (6, 12), (10, 5)]

    def _compare_pulse(self, series_list, parameters=None):
        cases = [dict(spo2=case_series, drop=drop, min_time=min_time, pulse=True) for case_series in series_list for drop, min_time in (parameters or self.PULSE_PARAMETERS)]
        got = self._run_js(cases)
        self.assertEqual(len(got), len(cases))
        for case, js_result in zip(cases, got):
            events = desaturation.detect_pulse_events(case["spo2"], drop=case["drop"], min_time=case["min_time"])
            python_result = json.loads(json.dumps({"events": events, "summary": desaturation.summarize_pulse(case["spo2"], events)}))
            where = f"pulse drop={case['drop']} min_time={case['min_time']} series={case['spo2']}"
            self.assertEqual(js_result["events"], python_result["events"], where)
            self.assertEqual(js_result["summary"], python_result["summary"], where)

    def test_pulse_cases_above_100_and_gaps(self):
        cases = [
            [140] * 20 + _fall(140, 6, 8) + [140] * 10,
            [70] * 20 + _fall(70, 6, 10) + [70] * 10,
            [70] * 20 + [70 + k for k in range(1, 11)] + [80] * 20,  # a rise is not an event
            [70] * 20 + _fall(70, 3, 5) + [None, 67] + _fall(67, 4, 5) + [70] * 10,
            [70] * 20 + _fall(70, 3, 5) + [255, 67] + _fall(67, 4, 5) + [70] * 10,
            [250] * 5 + _fall(250, 8, 10) + [254, 255, None, 0, 251, 252] + [200] * 5,
            [], [None] * 20, [255] * 20,
        ]
        self._compare_pulse(cases)
        got = self._run_js([dict(spo2=cases[0], drop=6, min_time=8, pulse=True)])[0]
        self.assertEqual(len(got["events"]), 1)

    def test_pulse_seeded_random_sequences(self):
        generator = random.Random(30)
        series = []
        for case_series in _fuzz_cases(150, seed=30):
            offset = generator.choice((0, 40, 100, 160))  # lift into the pulse range, incl. above 100
            series.append([value if value is None or value in (127, 255) or value == 0 else value + offset for value in case_series])
        self.assertGreater(sum(len(desaturation.detect_pulse_events(pulse_series)) for pulse_series in series), 30)
        self._compare_pulse(series, self.PULSE_PARAMETERS[:2])


if __name__ == "__main__":
    unittest.main()
