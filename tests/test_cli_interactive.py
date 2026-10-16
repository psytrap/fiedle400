"""Unit tests for PO-400 interactive CLI wizard, range parsing, and ISO filename generation."""

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest.mock import MagicMock, patch

from fiedle400 import protocol
from fiedle400.cli import generate_iso_filename, parse_session_selection, run_interactive_wizard

HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


class TestCliInteractive(unittest.TestCase):
    """Test suite for interactive CLI workflow and helpers."""

    def setUp(self):
        self.s1 = protocol.SessionInfo(
            session_id=1,
            user_id=1,
            record_count=100,
            duration_sec=100,
            timestamp=datetime(2026, 9, 6, 10, 0, 0),
        )
        self.s2 = protocol.SessionInfo(
            session_id=2,
            user_id=1,
            record_count=200,
            duration_sec=200,
            timestamp=datetime(2026, 9, 6, 11, 0, 0),
        )
        self.s3 = protocol.SessionInfo(
            session_id=3,
            user_id=1,
            record_count=300,
            duration_sec=300,
            timestamp=datetime(2026, 9, 6, 12, 0, 0),
        )
        self.s4 = protocol.SessionInfo(
            session_id=4,
            user_id=1,
            record_count=400,
            duration_sec=400,
            timestamp=datetime(2026, 9, 6, 13, 0, 0),
        )
        self.sessions = [self.s1, self.s2, self.s3, self.s4]

    def test_parse_single_session(self):
        res = parse_session_selection("2", self.sessions)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].session_id, 2)

    def test_parse_comma_list(self):
        res = parse_session_selection("1, 3, 4", self.sessions)
        self.assertEqual([s.session_id for s in res], [1, 3, 4])

    def test_parse_range(self):
        res = parse_session_selection("2-4", self.sessions)
        self.assertEqual([s.session_id for s in res], [2, 3, 4])

    def test_parse_range_and_list_combined(self):
        res = parse_session_selection("1-2, 4", self.sessions)
        self.assertEqual([s.session_id for s in res], [1, 2, 4])

    def test_parse_all_keywords(self):
        for kw in ("a", "A", "all", "ALL"):
            res = parse_session_selection(kw, self.sessions)
            self.assertEqual(len(res), 4)

    def test_parse_invalid_inputs(self):
        with self.assertRaises(ValueError):
            parse_session_selection("", self.sessions)

        with self.assertRaises(ValueError):
            parse_session_selection("99", self.sessions)

        with self.assertRaises(ValueError):
            parse_session_selection("3-1", self.sessions)

        with self.assertRaises(ValueError):
            parse_session_selection("abc", self.sessions)

    def test_generate_iso_filename_single(self):
        fn = generate_iso_filename([self.s1])
        # s1: 10:00:00 + 100s = 10:01:40 (default ext is spo2)
        self.assertEqual(fn, "fiedle400_2026-09-06T100000_2026-09-06T100140.spo2")
        # test explicit csv extension
        fn_csv = generate_iso_filename([self.s1], ext="csv")
        self.assertEqual(fn_csv, "fiedle400_2026-09-06T100000_2026-09-06T100140.csv")

    def test_generate_iso_filename_multiple(self):
        fn = generate_iso_filename([self.s1, self.s3])
        # s1 starts at 10:00:00; s3 ends at 12:00:00 + 300s = 12:05:00
        self.assertEqual(fn, "fiedle400_2026-09-06T100000_2026-09-06T120500.spo2")

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["q"])
    def test_wizard_quit(self, mock_input, mock_engine_cls, mock_dev_cls):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(serial_number="50F123", firmware_version="v2.0"),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)
        mock_dev.close.assert_called()

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["q"])
    def test_wizard_does_not_invent_unreported_device_details(self, mock_input, mock_engine_cls, mock_dev_cls):
        """The real device reports no firmware version or serial (PROTOCOL.md §3.8): say so, don't print defaults."""
        mock_dev_cls.return_value.connect.return_value = "/dev/hidraw_test"
        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(hardware_id="50F", user_profile="user"),
            "rtc_time_str": "not reported by the device",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        with patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(run_interactive_wizard(MagicMock(device=None, verbose=0)), 0)
        text = out.getvalue()
        self.assertIn("Firmware Version      : not reported by the device | Serial: not reported by the device", text)
        self.assertIn("Device Descriptor     : 50F", text)
        self.assertNotIn("v2.0", text)

    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.csv")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1-2", "", "", "y", "n"])
    def test_wizard_download_and_erase(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(serial_number="50F123", firmware_version="v2.0"),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)

        # Verified download of session 1 and 2
        self.assertEqual(mock_engine.download_session.call_count, 2)
        # Verified flash erase was called
        mock_engine.clear_memory.assert_called_with(0, debug=0)
        # Export called with both records combined
        mock_export.assert_called_once()
        args_export = mock_export.call_args[0]
        self.assertEqual(len(args_export[0]), 2)  # 2 sessions * 1 record each
        self.assertTrue(args_export[1].endswith(".spo2"))

    @unittest.skipUnless(HAS_MATPLOTLIB, "matplotlib not installed (optional 'plot' extra)")
    @patch("fiedle400.cli._open_in_viewer", return_value=True)
    @patch("fiedle400.plot.plot_session", return_value="/tmp/test.png")
    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.spo2")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1-2", "4", "", "", "y", "n"])
    def test_wizard_download_format_png_generates_plot(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export, mock_plot, mock_open):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)

        # png format writes the data to a scratch file just to feed the plot ...
        mock_export.assert_called_once()
        self.assertEqual(mock_export.call_args[0][2], "spo2")
        tmp_path = mock_export.call_args[0][1]
        self.assertTrue(tmp_path.endswith(".spo2"))
        # ... the plot is rendered from that same scratch file ...
        mock_plot.assert_called_once()
        plot_kwargs = mock_plot.call_args.kwargs
        self.assertEqual(plot_kwargs["filepath"], tmp_path)
        # ... "Save as" and the plot output stay .png, matching what was chosen ...
        self.assertTrue(plot_kwargs["output_png"].endswith(".png"))
        # ... and the scratch file does not survive a successful plot.
        self.assertFalse(os.path.exists(tmp_path))
        # Pressing Enter at "Open the plot now? [Y/n]" (default yes) opens the PNG.
        mock_open.assert_called_once_with("/tmp/test.png")

    def _run_png_wizard(self, open_answer, opener_result=True):
        """Runs the wizard's png path with a stubbed plot; returns (printed output, opener mock)."""
        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {"device_info": protocol.DeviceInfo(), "rtc_time_str": "x"}
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        answers = iter(["1-2", "4", "", open_answer, "n", "q"])
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            return next(answers)

        buf = io.StringIO()
        with patch("fiedle400.cli.PulsoxHidDevice"), \
                patch("fiedle400.cli.serial_engine.SerialDeviceEngine", return_value=mock_engine), \
                patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.spo2"), \
                patch("fiedle400.plot.plot_session", return_value="/tmp/test.png"), \
                patch("fiedle400.cli._open_in_viewer", return_value=opener_result) as opener, \
                patch("builtins.input", side_effect=fake_input), redirect_stdout(buf):
            run_interactive_wizard(MagicMock(device=None, verbose=0))
        return buf.getvalue() + "".join(prompts), opener

    @unittest.skipUnless(HAS_MATPLOTLIB, "matplotlib not installed (optional 'plot' extra)")
    def test_wizard_png_does_not_open_the_plot_when_declined(self):
        out, opener = self._run_png_wizard("n")
        self.assertIn("Open the plot now?", out)
        opener.assert_not_called()

    @unittest.skipUnless(HAS_MATPLOTLIB, "matplotlib not installed (optional 'plot' extra)")
    def test_wizard_png_names_the_file_when_no_viewer_can_be_opened(self):
        out, opener = self._run_png_wizard("y", opener_result=False)
        opener.assert_called_once_with("/tmp/test.png")
        self.assertIn("Could not open a viewer; the plot is at: /tmp/test.png", out)

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["q"])
    def test_wizard_header_shows_the_project_page(self, mock_input, mock_engine_cls, mock_dev_cls):
        mock_engine_cls.return_value.read_device_info.return_value = {"device_info": protocol.DeviceInfo(), "rtc_time_str": "x"}
        mock_engine_cls.return_value.list_sessions.return_value = self.sessions
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            run_interactive_wizard(MagicMock(device=None, verbose=0))
        self.assertIn("https://github.com/psytrap/fiedle400", out.getvalue())

    @patch("fiedle400.cli.shutil.copy")
    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.spo2")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1-2", "4", "", "y", "n"])
    def test_wizard_download_format_png_without_matplotlib(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export, mock_copy):
        import builtins as _builtins
        import sys as _sys

        real_import = _builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "matplotlib" or name.startswith("matplotlib."):
                raise ModuleNotFoundError("No module named 'matplotlib'", name="matplotlib")
            return real_import(name, *args, **kwargs)

        import fiedle400
        saved = {k: _sys.modules.pop(k) for k in list(_sys.modules) if k == "fiedle400.plot" or k.startswith("matplotlib")}
        saved_attr = vars(fiedle400).pop("plot", None)

        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        buf = io.StringIO()
        try:
            with patch("builtins.__import__", side_effect=fake_import), redirect_stdout(buf):
                args = MagicMock(device=None, verbose=0)
                ret = run_interactive_wizard(args)
        finally:
            _sys.modules.pop("fiedle400.plot", None)
            _sys.modules.update(saved)
            if saved_attr is not None:
                fiedle400.plot = saved_attr

        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("pip install matplotlib", out)
        self.assertIn("Saved the data instead so it isn't lost", out)
        mock_export.assert_called_once()  # the scratch save itself still succeeded
        # Falls back to persisting the data (as .spo2, next to the requested .png)
        # instead of losing the download when the plot can't be rendered.
        mock_copy.assert_called_once()
        fallback_fn = mock_copy.call_args[0][1]
        self.assertTrue(fallback_fn.endswith(".spo2"))

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["c", "y", "n"])
    def test_wizard_clear_from_menu(self, mock_input, mock_engine_cls, mock_dev_cls):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)
        mock_engine.clear_memory.assert_called_with(0, debug=0)

    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.spo2")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["", "", "", "", "n", "n"])
    def test_wizard_default_enter_downloads_all(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(serial_number="50F123", firmware_version="v2.0"),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)

        # Verified that ALL 4 sessions were downloaded when Enter was pressed on action prompt
        self.assertEqual(mock_engine.download_session.call_count, len(self.sessions))
        mock_export.assert_called_once()
        args_export = mock_export.call_args[0]
        self.assertEqual(len(args_export[0]), 4)
        self.assertTrue(args_export[1].endswith(".spo2"))

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["w", "n", "q"])
    def test_wizard_cancel(self, mock_input, mock_engine_cls, mock_dev_cls):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)
        mock_engine.download_session.assert_not_called()

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["\x1b[A\x1b[Bq"])
    def test_wizard_quit_with_ansi_escape_keys(self, mock_input, mock_engine_cls, mock_dev_cls):
        """Verifies that arrow keys (^[[A^[[B) preceding 'q' do not trigger 'Invalid session number'."""
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)
        mock_engine.download_session.assert_not_called()

    @patch("builtins.input", return_value="  \x1b[A\x1b[Bq  ")
    def test_clean_input_helper(self, mock_input):
        from fiedle400.cli import clean_input
        cleaned = clean_input()
        self.assertEqual(cleaned, "q")

    def test_parse_session_selection_with_ansi(self):
        res = parse_session_selection("\x1b[A1\x1b[B", self.sessions)
        self.assertEqual([s.session_id for s in res], [1])

        res_range = parse_session_selection("\x1b[C1-2\x1b[D", self.sessions)
        self.assertEqual([s.session_id for s in res_range], [1, 2])

    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["x", "q"])
    def test_wizard_unknown_action(self, mock_input, mock_engine_cls, mock_dev_cls):
        """Verifies that an unknown action like 'x' outputs 'Unknown action' and does not crash."""
        import io
        from contextlib import redirect_stdout

        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        buf = io.StringIO()
        args = MagicMock(device=None, verbose=0)
        with redirect_stdout(buf):
            ret = run_interactive_wizard(args)

        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("Unknown action: 'x'", out)
        self.assertNotIn("Invalid session number: 'x'", out)

    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test.spo2")
    @patch("os.path.exists", side_effect=[True, False, False, False])
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1", "", "", "y", "n", "n"])
    def test_wizard_overwrite_confirmed(self, mock_input, mock_engine_cls, mock_dev_cls, mock_exists, mock_export):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        args = MagicMock(device=None, verbose=0)
        ret = run_interactive_wizard(args)
        self.assertEqual(ret, 0)
        mock_export.assert_called_once()

    @patch("fiedle400.cli._export_records_to_file")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1", "", "", "n", "q", "q"])
    def test_wizard_overwrite_cancelled(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine_cls.return_value = mock_engine

        def fake_exists(p):
            return p.endswith(".spo2") and "_1" not in p

        with patch("os.path.exists", side_effect=fake_exists):
            args = MagicMock(device=None, verbose=0)
            ret = run_interactive_wizard(args)

        self.assertEqual(ret, 0)
        mock_export.assert_not_called()

    @patch("fiedle400.cli._export_records_to_file", return_value="/tmp/test_1.spo2")
    @patch("fiedle400.cli.PulsoxHidDevice")
    @patch("fiedle400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1", "", "", "n", "", "n", "n"])
    def test_wizard_overwrite_accepts_suggested_suffix(self, mock_input, mock_engine_cls, mock_dev_cls, mock_export):
        mock_dev = MagicMock()
        mock_dev.connect.return_value = "/dev/hidraw_test"
        mock_dev_cls.return_value = mock_dev

        mock_engine = MagicMock()
        mock_engine.read_device_info.return_value = {
            "device_info": protocol.DeviceInfo(),
            "rtc_time_str": "2026-09-06 12:00:00",
        }
        mock_engine.list_sessions.return_value = self.sessions
        mock_engine.download_session.return_value = [{"spo2": 98, "heart_rate": 65}]
        mock_engine_cls.return_value = mock_engine

        # Mock os.path.exists so that initial file exists, but suffixed _1 does not
        orig_exists = os.path.exists
        def fake_exists(p):
            if "_1.spo2" in p:
                return False
            if p.endswith(".spo2"):
                return True
            return orig_exists(p)

        with patch("os.path.exists", side_effect=fake_exists):
            args = MagicMock(device=None, verbose=0)
            ret = run_interactive_wizard(args)

        self.assertEqual(ret, 0)
        mock_export.assert_called_once()
        saved_fn = mock_export.call_args[0][1]
        self.assertTrue(saved_fn.endswith("_1.spo2"))

    def test_get_next_available_filename(self):
        import tempfile
        from fiedle400.cli import get_next_available_filename

        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = os.path.join(tmpdir, "rec.spo2")
            # When file does not exist, returns original
            self.assertEqual(get_next_available_filename(f0), f0)

            # Create rec.spo2 -> should return rec_1.spo2
            with open(f0, "w") as f:
                f.write("0")
            self.assertEqual(get_next_available_filename(f0), os.path.join(tmpdir, "rec_1.spo2"))

            # Create rec_1.spo2 -> should return rec_2.spo2
            f1 = os.path.join(tmpdir, "rec_1.spo2")
            with open(f1, "w") as f:
                f.write("1")
            self.assertEqual(get_next_available_filename(f0), os.path.join(tmpdir, "rec_2.spo2"))

            # Also starting from rec_1.spo2 directly should increment to rec_2.spo2
            self.assertEqual(get_next_available_filename(f1), os.path.join(tmpdir, "rec_2.spo2"))

            # Create rec_2.spo2 -> should return rec_3.spo2
            f2 = os.path.join(tmpdir, "rec_2.spo2")
            with open(f2, "w") as f:
                f.write("2")
            self.assertEqual(get_next_available_filename(f0), os.path.join(tmpdir, "rec_3.spo2"))


if __name__ == "__main__":
    unittest.main()
