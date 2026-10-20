"""Readers for recordings on disk (recording.py) and the `view` command (T-013)."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import scrub_env  # noqa: E402
from fiedle400 import cli, export, recording  # noqa: E402

RECORDS = [
    {"timestamp": "2026-10-01T22:00:00", "spo2": 97, "heart_rate": 60, "flags": None},
    {"timestamp": "2026-10-01T22:00:01", "spo2": 96, "heart_rate": 61, "flags": None},
    {"timestamp": "2026-10-01T22:00:02", "spo2": None, "heart_rate": None, "flags": "probe-out"},
    {"timestamp": "2026-10-01T22:00:03", "spo2": 95, "heart_rate": 62, "flags": None},
]


def _strip(records):
    return [{k: r[k] for k in ("timestamp", "spo2", "heart_rate", "flags")} for r in records]


class TestReaders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def _write(self, name, data=b""):
        path = os.path.join(self.dir, name)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(path, mode) as f:
            f.write(data)
        return path

    def test_spo2_round_trip_including_a_probe_out_second(self):
        path = self._write("a.spo2", export.build_spo2_binary(RECORDS))
        start, records = recording.load_session_file(path)
        self.assertEqual(start, datetime(2026, 10, 1, 22, 0, 0))
        self.assertEqual(records, RECORDS)

    def test_csv_round_trip(self):
        path = export.export_records(RECORDS, os.path.join(self.dir, "a.csv"))
        start, records = recording.load_session_file(path)
        self.assertEqual(start, datetime(2026, 10, 1, 22, 0, 0))
        self.assertEqual(records, RECORDS)

    def test_json_round_trip(self):
        path = export.export_records(RECORDS, os.path.join(self.dir, "a.json"))
        start, records = recording.load_session_file(path)
        self.assertEqual(start, datetime(2026, 10, 1, 22, 0, 0))
        self.assertEqual(_strip(records), RECORDS)

    def test_missing_first_timestamp_is_an_error(self):
        path = self._write("a.json", json.dumps([{"spo2": 97, "heart_rate": 60}]))
        with self.assertRaisesRegex(ValueError, "no timestamp"):
            recording.load_session_file(path)

    def test_unknown_extension_is_an_error(self):
        path = self._write("a.txt", "x")
        with self.assertRaisesRegex(ValueError, "Unsupported file format"):
            recording.load_session_file(path)

    def test_missing_file_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            recording.load_session_file(os.path.join(self.dir, "nope.spo2"))

    def test_truncated_spo2_is_an_error(self):
        path = self._write("a.spo2", b"\x58\x03")
        with self.assertRaisesRegex(ValueError, "too small"):
            recording.load_session_file(path)

    def test_find_latest_picks_newest_and_ignores_other_extensions(self):
        old = self._write("old.csv", "x")
        new = self._write("new.json", "[]")
        other = self._write("newest.txt", "x")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        os.utime(other, (3000, 3000))
        self.assertEqual(recording.find_latest_session_file(self.dir), os.path.abspath(new))

    def test_find_latest_returns_none_without_recordings(self):
        self._write("notes.txt", "x")
        self.assertIsNone(recording.find_latest_session_file(self.dir))

    def test_module_imports_without_matplotlib(self):
        code = ("import sys; sys.modules['matplotlib'] = None\n"
                "import fiedle400.recording")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=dict(os.environ, PYTHONPATH=root), cwd=root)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestViewCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        scrub_env()
        self.rec = os.path.join(self.dir, "night.spo2")
        with open(self.rec, "wb") as f:
            f.write(export.build_spo2_binary(RECORDS))

    def _view(self, argv, opener_result=True):
        out = io.StringIO()
        with mock.patch("fiedle400.cli._open_in_viewer", return_value=opener_result) as opener, \
                mock.patch("fiedle400.cli.time.sleep"), \
                redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            cli.main(["view"] + argv)
        return cm.exception.code, out.getvalue(), opener

    def test_default_opens_a_temporary_page_and_leaves_no_file_behind(self):
        seen = {}

        def opener(path):
            seen["path"] = path
            with open(path, encoding="utf-8") as f:
                seen["html"] = f.read()
            return True

        out = io.StringIO()
        with mock.patch("fiedle400.cli._open_in_viewer", side_effect=opener), \
                mock.patch("fiedle400.cli.time.sleep"), redirect_stdout(out), \
                self.assertRaises(SystemExit) as cm:
            cli.main(["view", self.rec])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(os.path.dirname(seen["path"]), self.dir)  # the recording's folder
        self.assertTrue(seen["path"].endswith(".html"))
        self.assertIn("2026-10-01T22:00:03", seen["html"])  # the data is in the page
        self.assertEqual(os.listdir(self.dir), ["night.spo2"])  # temp page removed

    def test_no_browser_names_the_recording(self):
        code, out, opener = self._view([self.rec], opener_result=False)
        self.assertEqual(code, 0)
        opener.assert_called_once()
        self.assertIn(f"Could not open a viewer; the data is still at: {self.rec}", out)
        self.assertEqual(os.listdir(self.dir), ["night.spo2"])

    def test_convert_writes_html_next_to_the_recording_without_opening(self):
        code, out, opener = self._view([self.rec, "--convert"])
        self.assertEqual(code, 0)
        opener.assert_not_called()
        page = os.path.join(self.dir, "night.html")
        self.assertIn(page, out)
        with open(page, encoding="utf-8") as f:
            self.assertIn("2026-10-01T22:00:03", f.read())

    def test_convert_with_output(self):
        target = os.path.join(self.dir, "sub", "x.html")
        os.makedirs(os.path.dirname(target))
        code, out, opener = self._view([self.rec, "--convert", "-o", target])
        self.assertEqual(code, 0)
        opener.assert_not_called()
        self.assertTrue(os.path.isfile(target))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "night.html")))

    def test_output_without_convert_is_one_line_error(self):
        code, out, opener = self._view([self.rec, "-o", os.path.join(self.dir, "x.html")])
        self.assertEqual(code, 1)
        opener.assert_not_called()
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("--convert", out)

    def test_without_file_uses_the_latest_in_the_current_directory(self):
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.dir)
        with mock.patch("fiedle400.cli.config.get_workdir", return_value=None):
            code, out, opener = self._view(["--convert"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "night.html")))

    def test_no_recording_found_is_one_line_error(self):
        empty = os.path.join(self.dir, "empty")
        os.makedirs(empty)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(empty)
        with mock.patch("fiedle400.cli.config.get_workdir", return_value=None):
            code, out, opener = self._view([])
        self.assertEqual(code, 1)
        opener.assert_not_called()
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("No recording", out)

    def test_unreadable_file_is_one_line_error(self):
        bad = os.path.join(self.dir, "bad.spo2")
        with open(bad, "wb") as f:
            f.write(b"junk")
        code, out, opener = self._view([bad])
        self.assertEqual(code, 1)
        opener.assert_not_called()
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("Cannot read", out)

    def test_missing_file_is_one_line_error(self):
        code, out, opener = self._view([os.path.join(self.dir, "nope.csv")])
        self.assertEqual(code, 1)
        self.assertEqual(len(out.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
