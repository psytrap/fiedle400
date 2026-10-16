"""The CLI exits with a short message instead of a traceback when something goes wrong."""

import builtins
import io
import os
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


class TestPlotWithoutMatplotlib(unittest.TestCase):
    def test_plot_prints_install_hint(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "matplotlib" or name.startswith("matplotlib."):
                raise ModuleNotFoundError("No module named 'matplotlib'", name="matplotlib")
            return real_import(name, *args, **kwargs)

        import fiedle400
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "fiedle400.plot" or k.startswith("matplotlib")}
        saved_attr = vars(fiedle400).pop("plot", None)
        try:
            out = io.StringIO()
            with mock.patch("builtins.__import__", side_effect=fake_import), redirect_stdout(out):
                rc = cli.command_plot(SimpleNamespace(file=None, output=None, dpi=100))
        finally:
            sys.modules.pop("fiedle400.plot", None)
            sys.modules.update(saved)
            if saved_attr is not None:
                fiedle400.plot = saved_attr
        self.assertEqual(rc, 1)
        self.assertIn("pip install matplotlib", out.getvalue())

    def test_package_import_does_not_need_matplotlib(self):
        import fiedle400
        self.assertNotIn("plot_session", vars(fiedle400))  # lazy, resolved via __getattr__


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


if __name__ == "__main__":
    unittest.main()


class TestOpenInViewer(unittest.TestCase):
    """_open_in_viewer uses the OS's own opener and never raises."""

    def test_linux_runs_xdg_open(self):
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch("fiedle400.cli.shutil.which", return_value="/usr/bin/xdg-open"), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertTrue(cli._open_in_viewer("/tmp/a.png"))
        self.assertEqual(popen.call_args[0][0], ["xdg-open", "/tmp/a.png"])

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
                mock.patch("fiedle400.cli.shutil.which", return_value=None), \
                mock.patch("fiedle400.cli.subprocess.Popen") as popen:
            self.assertFalse(cli._open_in_viewer("/tmp/a.png"))
        popen.assert_not_called()

    def test_os_error_returns_false(self):
        with mock.patch.object(sys, "platform", "linux"), \
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
