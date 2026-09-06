"""Unit tests for PO-400 interactive CLI wizard, range parsing, and ISO filename generation."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from po400 import protocol
from po400.cli import generate_iso_filename, parse_session_selection, run_interactive_wizard


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
        # s1: 10:00:00 + 100s = 10:01:40
        self.assertEqual(fn, "po400_2026-09-06T100000_2026-09-06T100140.csv")

    def test_generate_iso_filename_multiple(self):
        fn = generate_iso_filename([self.s1, self.s3])
        # s1 starts at 10:00:00; s3 ends at 12:00:00 + 300s = 12:05:00
        self.assertEqual(fn, "po400_2026-09-06T100000_2026-09-06T120500.csv")

    @patch("po400.cli.PulsoxHidDevice")
    @patch("po400.cli.serial_engine.SerialDeviceEngine")
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

    @patch("po400.cli._export_records_to_file", return_value="/tmp/test.csv")
    @patch("po400.cli.PulsoxHidDevice")
    @patch("po400.cli.serial_engine.SerialDeviceEngine")
    @patch("builtins.input", side_effect=["1-2", "", "y", "n"])
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
        self.assertTrue(args_export[1].endswith(".csv"))

    @patch("po400.cli.PulsoxHidDevice")
    @patch("po400.cli.serial_engine.SerialDeviceEngine")
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


if __name__ == "__main__":
    unittest.main()
