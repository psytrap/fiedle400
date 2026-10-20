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

    def test_time_below_level_is_adjustable_and_defaults_to_90(self):
        self.assertIn('id="desatLevel"', self.html)
        self.assertIn('value="90"', self.html)

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

    def test_basal_spo2_is_labelled_as_an_estimate(self):
        self.assertIn("Basal SpO2 (estimate)", spo2_viewer.build_viewer_html([]))


if __name__ == "__main__":
    unittest.main()
