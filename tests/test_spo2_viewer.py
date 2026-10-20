"""The self-contained HTML .spo2 viewer (T-005): one bundled template, the
specific recording's records injected as inline JSON at build time."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fiedle400 import spo2_viewer  # noqa: E402


class TestBuildViewerHtml(unittest.TestCase):
    def test_injects_records_as_parseable_json(self):
        records = [
            {"timestamp": "2026-10-19T10:00:00", "spo2": 98, "heart_rate": 65, "flags": "ok"},
            {"timestamp": "2026-10-19T10:00:01", "spo2": None, "heart_rate": None, "flags": "probe-out"},
        ]
        html = spo2_viewer.build_viewer_html(records)
        self.assertIn('id="spo2-data"', html)

        start = html.index('<script id="spo2-data" type="application/json">') + len(
            '<script id="spo2-data" type="application/json">'
        )
        end = html.index("</script>", start)
        payload = json.loads(html[start:end])

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["spo2"], 98)
        self.assertEqual(payload[0]["heart_rate"], 65)
        self.assertIsNone(payload[1]["spo2"])

    def test_drops_fields_the_template_does_not_use(self):
        records = [{"timestamp": "t", "spo2": 1, "heart_rate": 2, "flags": "ok", "session_id": 99, "block_id": 3}]
        html = spo2_viewer.build_viewer_html(records)
        self.assertNotIn("session_id", html)
        self.assertNotIn("block_id", html)

    def test_escapes_less_than_so_script_tag_cannot_be_closed_early(self):
        # No real field contains "</script>", but the escaping must hold even if one did.
        # Escaping just the leading "<" is sufficient: the browser's HTML parser only
        # recognizes a closing tag starting with a literal "<", so "\u003c/script>" is inert.
        records = [{"timestamp": "</script><script>evil()</script>", "spo2": 1, "heart_rate": 1, "flags": "ok"}]
        html = spo2_viewer.build_viewer_html(records)
        start = html.index('<script id="spo2-data" type="application/json">') + len(
            '<script id="spo2-data" type="application/json">'
        )
        end = html.index("</script>", start)
        data_blob = html[start:end]
        self.assertNotIn("</script", data_blob.lower())
        self.assertIn("\\u003c/script>\\u003cscript>evil()\\u003c/script>", data_blob)

    def test_empty_recording_still_produces_valid_html(self):
        html = spo2_viewer.build_viewer_html([])
        self.assertIn("<html>", html)
        start = html.index('<script id="spo2-data" type="application/json">') + len(
            '<script id="spo2-data" type="application/json">'
        )
        end = html.index("</script>", start)
        self.assertEqual(json.loads(html[start:end]), [])


class TestViewerControls(unittest.TestCase):
    """Markup the T-008 controls rely on. The behaviour itself needs a browser,
    which CI does not have; these only pin that the controls and the print
    stylesheet are in the generated page (checked by hand in a real browser)."""

    def setUp(self):
        self.html = spo2_viewer.build_viewer_html([])

    def test_has_a_switch_per_channel(self):
        self.assertIn('id="showSpo2"', self.html)
        self.assertIn('id="showHr"', self.html)

    def test_has_print_button_and_print_stylesheet(self):
        self.assertIn('id="printBtn"', self.html)
        self.assertIn("window.print()", self.html)
        self.assertIn("@media print", self.html)

    def test_time_below_level_has_no_input_of_its_own(self):
        # "Time below level" used to be its own independently adjustable
        # input (T-008, defaulting to 90%, before desaturation events
        # existed at all). The real SpO2 Assistant has no such separate
        # control -- "Time (min) <88%" uses the same desaturation criteria
        # level that classifies event severity (SPO2_FORMAT.md Sec7.1). Fixed
        # to match: no separate #desatLevel input any more.
        self.assertNotIn('id="desatLevel"', self.html)

    def test_time_below_level_uses_the_criteria_level(self):
        self.assertIn("analysis.params.criteria", self.html)

    def test_page_loads_nothing_from_the_network(self):
        for needle in ("http://", "https://", "src=\"//"):
            self.assertNotIn(needle, self.html)


class TestViewerDesaturationEvents(unittest.TestCase):
    """T-018: events are computed in Python and injected next to the records."""

    def _analysis(self, html):
        tag = '<script id="spo2-events" type="application/json">'
        start = html.index(tag) + len(tag)
        return json.loads(html[start:html.index("</script>", start)])

    def test_events_and_summary_are_injected(self):
        spo2 = [97] * 30 + [96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93] + [95, 97] * 5
        records = [{"timestamp": "t%d" % i, "spo2": v, "heart_rate": 70, "flags": "ok"} for i, v in enumerate(spo2)]
        analysis = self._analysis(spo2_viewer.build_viewer_html(records))
        self.assertEqual(len(analysis["events"]), 1)
        self.assertEqual(analysis["summary"]["total_event"], 1)
        self.assertEqual(analysis["params"]["drop"], 4)

    def test_empty_recording_has_an_analysis_block(self):
        analysis = self._analysis(spo2_viewer.build_viewer_html([]))
        self.assertEqual(analysis["events"], [])

    def test_basal_spo2_is_no_longer_labelled_as_an_estimate(self):
        # T-031 decoded the program's rule, which is the one desat.py uses.
        html = spo2_viewer.build_viewer_html([])
        self.assertIn("'Basal SpO2'", html)
        self.assertNotIn("estimate", html)


class TestViewerAcrossSessionGap(unittest.TestCase):
    """T-022: two stored sessions with a real pause between them must not give a false
    event across the pause, in the chart data or in the statistics."""

    def _two_sessions(self):
        def r(ts, v):
            return {"timestamp": ts, "spo2": v, "heart_rate": 70, "flags": "ok"}
        s1 = [98] * 30 + [98, 98, 98, 98, 97, 97, 97, 97]
        s2 = [96, 96, 95, 95, 95, 94, 94] + [97] * 30
        recs = [r("2026-10-16T08:37:%02d" % (31 + i) if i < 29 else "2026-10-16T08:38:%02d" % (i - 29), v)
                for i, v in enumerate(s1)]
        recs += [r("2026-10-16T08:41:%02d" % (10 + i) if i < 50 else "2026-10-16T08:42:%02d" % (i - 50), v)
                 for i, v in enumerate(s2)]
        return recs

    def _blocks(self, html):
        out = []
        for tag in ('<script id="spo2-data" type="application/json">',
                    '<script id="spo2-events" type="application/json">'):
            start = html.index(tag) + len(tag)
            out.append(json.loads(html[start:html.index("</script>", start)]))
        return out

    def test_no_false_event_across_the_pause(self):
        from fiedle400 import desat
        recs = self._two_sessions()
        # What the viewer used to see: the sessions side by side, an event across the join.
        self.assertEqual(len(desat.detect_events([r["spo2"] for r in recs])), 1)
        data, analysis = self._blocks(spo2_viewer.build_viewer_html(recs))
        self.assertEqual(analysis["events"], [])
        self.assertEqual(analysis["summary"]["total_event"], 0)

    def test_chart_data_has_one_entry_per_elapsed_second(self):
        data, _ = self._blocks(spo2_viewer.build_viewer_html(self._two_sessions()))
        # 08:37:31 .. 08:41:46 inclusive is 256 s; the pause is probe-out.
        self.assertEqual(len(data), 256)
        self.assertEqual(data[40]["flags"], "probe-out")
        self.assertIsNone(data[40]["spo2"])


class TestViewerConfigurableEventParameters(unittest.TestCase):
    """T-025: the desaturation-event parameters (drop %, min duration, criteria
    level) are adjustable inputs in the page, pre-filled from the same values
    desat.py used to compute the page's initial `analysis` block -- not
    hardcoded separately, which would let the two drift apart. The actual
    live-recompute behaviour (detectEvents/summarizeEvents, a JS port of
    desat.py) needs a browser and was verified by hand against the T-019
    probe recording: drop=3 -> 8 events, min_time=8 -> 9 events, both an
    exact match to the real SpO2 Assistant numbers from that ticket."""

    def setUp(self):
        self.html = spo2_viewer.build_viewer_html([])

    def test_has_an_input_per_parameter(self):
        self.assertIn('id="dropPct"', self.html)
        self.assertIn('id="minDur"', self.html)
        self.assertIn('id="critLevel"', self.html)

    def test_ranges_match_the_real_spo2_assistant_dialog(self):
        self.assertIn('id="dropPct" min="1" max="20"', self.html)
        self.assertIn('id="minDur" min="1" max="180"', self.html)
        self.assertIn('id="critLevel" min="1" max="99"', self.html)

    def test_defaults_are_not_hardcoded_separately_from_desat_py(self):
        # No value="..." on these inputs in the template itself -- they're set
        # from analysis.params in JS, so desat.py's constants stay the one
        # source of truth for the page's initial numbers.
        for input_id in ("dropPct", "minDur", "critLevel"):
            self.assertNotRegex(self.html, r'id="%s"[^>]*value=' % input_id)
        self.assertIn("document.getElementById('dropPct').value = analysis.params.drop", self.html)
        self.assertIn("document.getElementById('minDur').value = analysis.params.min_time", self.html)
        self.assertIn("document.getElementById('critLevel').value = analysis.params.criteria", self.html)

    def test_pulse_rate_events_explicitly_noted_as_not_shown(self):
        # T-029 decoded the pulse-event detector, but the viewer does not show
        # pulse events until T-030; the SpO2 row must say so (the pulse row
        # itself is covered by TestViewerDummyPulseInputs).
        self.assertIn("pulse-rate events: decoded, not shown yet", self.html)

    def test_inputs_recompute_on_change(self):
        self.assertIn("addEventListener('input', recomputeEvents)", self.html)


class TestViewerDummyPulseInputs(unittest.TestCase):
    """Placeholder pulse-rate parameter inputs matching SpO2 Assistant's own
    "Pulsrate Parameter" dialog section, added so the layout can be reviewed
    before T-029/T-030 decode and implement the real detector. Explicitly
    disabled and labelled dummy -- no detector exists yet (see T-025/T-028's
    original "not decoded" decision), so these must never look functional."""

    def setUp(self):
        self.html = spo2_viewer.build_viewer_html([])

    def test_has_an_input_per_pulse_parameter(self):
        self.assertIn('id="pulseDropBpm"', self.html)
        self.assertIn('id="pulseMinDur"', self.html)

    def test_inputs_are_disabled(self):
        self.assertRegex(self.html, r'id="pulseDropBpm"[^>]*\bdisabled\b')
        self.assertRegex(self.html, r'id="pulseMinDur"[^>]*\bdisabled\b')

    def test_marked_as_dummy_not_functional(self):
        self.assertIn("dummy", self.html.lower())
        self.assertIn("not functional", self.html.lower())
        self.assertIn("T-029", self.html)
        self.assertIn("T-030", self.html)

    def test_defaults_match_the_real_spo2_assistant_dialog(self):
        # Captured live against the T-019 probe recording (screenshot):
        # Pulsaenderung fuer Ereignis 6 bpm, Minimum Ereignisdauer 8 s.
        self.assertIn('id="pulseDropBpm" min="2" max="20" step="1" value="6"', self.html)
        self.assertIn('id="pulseMinDur" min="1" max="180" step="1" value="8"', self.html)

    def test_not_wired_to_any_recompute(self):
        # Dummy inputs must not trigger recomputeEvents -- there is nothing
        # for them to recompute.
        self.assertNotIn("pulseDropBpm').addEventListener", self.html)
        self.assertNotIn("pulseMinDur').addEventListener", self.html)


if __name__ == "__main__":
    unittest.main()
