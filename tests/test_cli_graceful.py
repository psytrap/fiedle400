"""The CLI exits with a short message instead of a traceback when something goes wrong."""

import io
import ntpath
import os
import posixpath
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import scrub_env  # noqa: E402
from fiedle400 import cli  # noqa: E402


class TestRunGuarded(unittest.TestCase):
    def test_unexpected_error_returns_1_with_message(self):
        def boom(args):
            raise OSError("device unplugged")

        err = io.StringIO()
        with redirect_stderr(err), mock.patch.dict(os.environ):
            scrub_env()
            rc = cli.run_guarded(boom, SimpleNamespace())
        self.assertEqual(rc, 1)
        self.assertIn("OSError: device unplugged", err.getvalue())
        self.assertIn("FIEDLE400_DEBUG=1", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_debug_env_reraises(self):
        def boom(args):
            raise ValueError("bad frame")

        with mock.patch.dict(os.environ, {"FIEDLE400_DEBUG": "1"}), self.assertRaises(ValueError):
            cli.run_guarded(boom, SimpleNamespace())

    def test_keyboard_interrupt_returns_130(self):
        def interrupted(args):
            raise KeyboardInterrupt

        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.run_guarded(interrupted, SimpleNamespace()), 130)

    def test_handler_return_code_passes_through(self):
        self.assertEqual(cli.run_guarded(lambda a: 0, SimpleNamespace()), 0)
        self.assertEqual(cli.run_guarded(lambda a: 3, SimpleNamespace()), 3)

    def test_main_routes_subcommand_through_guard(self):
        with mock.patch.object(cli, "command_read_time", side_effect=RuntimeError("no ack")), \
                redirect_stderr(io.StringIO()) as err, mock.patch.dict(os.environ), \
                self.assertRaises(SystemExit) as cm:
            scrub_env()
            cli.main(["read-time"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("RuntimeError: no ack", err.getvalue())


class TestWithoutMatplotlib(unittest.TestCase):
    """matplotlib is not a dependency any more (T-006): nothing may import it."""

    def test_package_import_and_view_help_work_without_matplotlib(self):
        import subprocess
        code = (
            "import sys; sys.modules['matplotlib'] = None\n"  # any import of it raises ImportError
            "import fiedle400\n"
            "from fiedle400 import cli\n"
            "try:\n"
            "    cli.main(['view', '--help'])\n"
            "except SystemExit as e:\n"
            "    sys.exit(e.code)\n"
        )
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONPATH=root)
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--convert", proc.stdout)

    def test_plot_session_is_gone(self):
        import fiedle400
        self.assertFalse(hasattr(fiedle400, "plot_session"))
        self.assertNotIn("plot_session", fiedle400.__all__)


class TestDownloadDefaultFormat(unittest.TestCase):
    """T-012: `download` writes the HTML viewer page by default, never a .spo2 unless asked."""

    RECORDS = [
        {"timestamp": "2026-10-01T22:00:00", "spo2": 97, "heart_rate": 60, "flags": None},
        {"timestamp": "2026-10-01T22:00:01", "spo2": 96, "heart_rate": 61, "flags": None},
    ]

    def _download(self, extra):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        engine = mock.MagicMock()
        engine.download_all_sessions.return_value = list(self.RECORDS)
        out = io.StringIO()
        with mock.patch.dict(os.environ), mock.patch("fiedle400.cli.PulsoxHidDevice"), \
                mock.patch("fiedle400.cli.serial_engine.SerialDeviceEngine", return_value=engine), \
                mock.patch("fiedle400.cli._open_in_viewer") as opener, \
                redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            scrub_env()
            cli.main(["download", "--workdir", tmp.name, *extra])
        self.assertEqual(cm.exception.code, 0)
        opener.assert_not_called()  # a non-interactive download never opens a browser
        return tmp.name, sorted(os.listdir(tmp.name))

    def test_default_is_one_html_file_with_the_records_and_no_spo2(self):
        folder, files = self._download([])
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith(".html"), files)
        with open(os.path.join(folder, files[0]), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("2026-10-01T22:00:01", html)

    def test_format_flag_still_writes_spo2(self):
        _, files = self._download(["-f", "spo2"])
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith(".spo2"), files)


class TestProbeOutAlert(unittest.TestCase):
    """RELEASE_PLAN.md T1's sentinel path has never been confirmed on real
    hardware; this alert exists so a real occurrence is impossible to miss."""

    def test_no_alert_when_no_probe_out_records(self):
        records = [{"flags": "ok", "spo2": 98, "heart_rate": 72}]
        self.assertIsNone(cli._probe_out_alert(records))

    def test_alert_fires_on_sentinel_probe_out(self):
        records = [
            {"flags": "ok", "spo2": 98, "heart_rate": 72},
            {"flags": "probe-out", "spo2": None, "heart_rate": None},
        ]
        alert = cli._probe_out_alert(records)
        self.assertIsNotNone(alert)
        self.assertIn("FINGER-OUT", alert)
        self.assertIn("T1", alert)
        self.assertIn("1 of 2", alert)

    def test_legacy_combined_flag_does_not_fire_the_alert(self):
        # The legacy flag-byte path ("probe-out,searching,low-perfusion") is a
        # different, already-verified code path (T1's table entry) -- this
        # alert is specifically about the sentinel-only "probe-out" string.
        records = [{"flags": "probe-out,searching,low-perfusion", "spo2": None, "heart_rate": None}]
        self.assertIsNone(cli._probe_out_alert(records))


class TestViewerTmpDir(unittest.TestCase):
    """_viewer_tmp_dir reuses the folder the .spo2 file was saved into,
    sidestepping a sandboxed browser's isolated /tmp and the hidden
    dot-directories a snap's home interface excludes -- both confirmed
    live against a real snap Firefox install to actually deny access."""

    def test_resolves_to_the_saved_files_own_directory(self):
        # Built relative and resolved through the real os.path, so the
        # expectation is correct on whichever OS this actually runs on
        # (T-062 -- a hardcoded POSIX literal here passed on Linux only
        # because os.path there happens to be posixpath already; it failed
        # on a real Windows machine for the wrong reason: os.path is bound
        # to ntpath/posixpath by the real OS, not by sys.platform).
        rel = os.path.join("home", "testuser", "Documents", "fiedle400")
        saved = os.path.join(rel, "rec.spo2")
        result = cli._viewer_tmp_dir(saved)
        self.assertEqual(result, os.path.abspath(rel))

    def test_bare_filename_resolves_to_the_current_directory_not_empty(self):
        result = cli._viewer_tmp_dir("rec.spo2")
        self.assertEqual(result, os.getcwd())

    def test_same_logic_on_posix_and_windows_path_styles(self):
        # Reusing the save folder needs no platform branch. Verified by
        # swapping in ntpath/posixpath directly (T-062) -- mocking
        # sys.platform, as this test used to, does not change which path
        # module os.path actually is, so it never exercised the other
        # style at all.
        for path_module in (posixpath, ntpath):
            fake_os = SimpleNamespace(path=path_module, getcwd=os.getcwd)
            with mock.patch.object(cli, "os", fake_os):
                saved = path_module.join("x", "y", "rec.spo2")
                expected = path_module.abspath(path_module.join("x", "y"))
                self.assertEqual(cli._viewer_tmp_dir(saved), expected)


class TestOpenInViewer(unittest.TestCase):
    """_open_in_viewer uses the OS's own opener and never raises.

    On Linux, it must prefer the real default *browser* (xdg-settings) over
    plain xdg-open, since xdg-open's text/html MIME association can drift to
    a non-browser (observed on a real machine: Thunderbird) independently of
    the actual default-browser setting -- see _resolve_linux_browser_argv's
    own docstring. Every Linux test here mocks subprocess.run (the
    xdg-settings lookup) explicitly rather than leaving it unmocked, since an
    unmocked call would hit this test machine's real, possibly-drifted MIME
    database and make the test non-deterministic.
    """

    def _no_browser_resolved(self):
        """A subprocess.run mock simulating xdg-settings being unavailable,
        so _resolve_linux_browser_argv returns None and the fallback path
        (plain xdg-open) is what gets exercised."""
        return mock.patch("fiedle400.cli.subprocess.run", side_effect=OSError("not found"))

    def test_linux_falls_back_to_xdg_open_when_browser_cannot_be_resolved(self):
        with mock.patch.object(sys, "platform", "linux"), \
                self._no_browser_resolved(), \
                mock.patch("fiedle400.cli.shutil.which", return_value="/usr/bin/xdg-open"), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertTrue(cli._open_in_viewer("/tmp/a.png"))
        self.assertEqual(popen.call_args[0][0], ["xdg-open", "/tmp/a.png"])

    def test_linux_resolves_the_real_default_browser_not_xdg_open(self):
        # Mirrors the real bug found live: xdg-mime's text/html association
        # had drifted to Thunderbird while xdg-settings default-web-browser
        # correctly still said Firefox. This test wires up exactly that --
        # the fix must use the browser, not whatever xdg-open would pick.
        run_result = mock.Mock(returncode=0, stdout="firefox_firefox.desktop\n")
        desktop_entry = "[Desktop Entry]\nExec=firefox %u\n"
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch("fiedle400.cli.subprocess.run", return_value=run_result), \
                mock.patch("os.path.isfile", side_effect=lambda p: p.endswith("firefox_firefox.desktop")), \
                mock.patch("builtins.open", mock.mock_open(read_data=desktop_entry)), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertTrue(cli._open_in_viewer("/tmp/viewer.html"))
        self.assertEqual(popen.call_args[0][0], ["firefox", "/tmp/viewer.html"])

    def test_linux_browser_resolution_strips_desktop_field_codes(self):
        run_result = mock.Mock(returncode=0, stdout="example_example.desktop\n")
        desktop_entry = "[Desktop Entry]\nExec=env SOMEVAR=1 example-browser --new-window %U\n"
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch("fiedle400.cli.subprocess.run", return_value=run_result), \
                mock.patch("os.path.isfile", return_value=True), \
                mock.patch("builtins.open", mock.mock_open(read_data=desktop_entry)), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertTrue(cli._open_in_viewer("/tmp/viewer.html"))
        self.assertEqual(
            popen.call_args[0][0],
            ["env", "SOMEVAR=1", "example-browser", "--new-window", "/tmp/viewer.html"],
        )

    def test_macos_runs_open(self):
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch("fiedle400.cli.shutil.which", return_value="/usr/bin/open"), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertTrue(cli._open_in_viewer("/tmp/a.png"))
        self.assertEqual(popen.call_args[0][0], ["open", "/tmp/a.png"])

    def test_windows_uses_startfile(self):
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(os, "startfile", create=True) as startfile:
            self.assertTrue(cli._open_in_viewer("C:/a.png"))
        startfile.assert_called_once_with("C:/a.png")

    def test_missing_opener_returns_false(self):
        with mock.patch.object(sys, "platform", "linux"), \
                self._no_browser_resolved(), \
                mock.patch("fiedle400.cli.shutil.which", return_value=None), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertFalse(cli._open_in_viewer("/tmp/a.png"))
        popen.assert_not_called()

    def test_os_error_returns_false(self):
        with mock.patch.object(sys, "platform", "linux"), \
                self._no_browser_resolved(), \
                mock.patch("fiedle400.cli.shutil.which", return_value="/usr/bin/xdg-open"), \
                mock.patch("fiedle400.cli.subprocess.Popen", side_effect=OSError("denied")):
            self.assertFalse(cli._open_in_viewer("/tmp/a.png"))


class TestHelpShowsProjectPage(unittest.TestCase):
    def test_help_ends_with_the_project_url(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            cli.main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("https://github.com/psytrap/fiedle400", out.getvalue())


if __name__ == "__main__":
    unittest.main()
