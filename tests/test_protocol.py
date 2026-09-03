import unittest
from datetime import datetime
from po400.protocol import (
    Commands,
    Parsers,
    Opcode,
    DataPoint,
    DeviceInfo,
    SessionInfo,
    decode_usb_vid_pid,
)


class TestProtocol(unittest.TestCase):

    def test_commands_build_hid(self):
        cmd = Commands.build_hid(0xAF)
        self.assertEqual(len(cmd), 64)
        self.assertEqual(cmd[0], 0x7D)
        self.assertEqual(cmd[1], 0x81)
        self.assertEqual(cmd[2], 0xAF)
        self.assertEqual(cmd[3], 0x80)

    def test_commands_unlock_handshake(self):
        cmd = Commands.unlock_handshake()
        self.assertEqual(len(cmd), 64)
        self.assertEqual(cmd[0], 0x7D)
        self.assertEqual(cmd[1], 0x81)
        self.assertEqual(cmd[2], Opcode.UNLOCK_HANDSHAKE)
        self.assertEqual(cmd[9], 0x7D)
        self.assertEqual(cmd[10], 0x81)
        self.assertEqual(cmd[11], Opcode.STORAGE_NEGOTIATION)

    def test_decode_usb_vid_pid(self):
        arch, src = decode_usb_vid_pid("28E9", "028A")
        self.assertIn("GigaDevice MCU HID Oximeter", arch)
        self.assertIn("hid_device.inf", src)

    def test_parsers_device_info(self):
        report_ver = bytes([0xF0, 0x70, 2, 0, 7] + [0]*59)
        info_ver = Parsers.parse_device_info(report_ver)
        self.assertEqual(info_ver.firmware_version, "v2.0.7")

        report_zero = bytes([0xF0, 0x70, 0, 0, 0] + [0]*59)
        info_zero = Parsers.parse_device_info(report_zero)
        self.assertIsNone(info_zero.firmware_version)

    def test_parsers_session_index(self):
        report = bytes([0xF0, 0x70, 1, 1, 1, 0, 120, 26, 9, 2, 8, 0, 0] + [0]*51)
        sessions = Parsers.parse_session_index(report)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, 1)
        self.assertEqual(sessions[0].user_id, 1)
        self.assertEqual(sessions[0].record_count, 120)

        zero_report = bytes([0xF0, 0x70, 0] + [0]*61)
        zero_sessions = Parsers.parse_session_index(zero_report)
        self.assertEqual(len(zero_sessions), 0)

    def test_parsers_hid_chunks(self):
        chunk0 = [0xF0, 0x00, 0x10, 85, 0, 0]
        chunk1 = [0xF0, 0x01, 0x10, 72, 98, 0]
        raw_report = bytes(chunk0 + chunk1)
        now = datetime.now()

        datapoints, latest_spo2, latest_hr, latest_ppg = Parsers.parse_hid_chunks(raw_report, now)
        self.assertEqual(len(datapoints), 2)
        self.assertEqual(latest_spo2, 98)
        self.assertEqual(latest_hr, 72)
        self.assertEqual(latest_ppg, 85)

    def test_parsers_stored_data_frames(self):
        frame = bytes([0x81, 98, 72])
        now = datetime.now()
        datapoints = Parsers.parse_stored_data_frames(frame, now)
        self.assertEqual(len(datapoints), 1)
        self.assertEqual(datapoints[0].spo2, 98)

        finger_off_frame = bytes([0xA0, 98, 72])
        dps_off = Parsers.parse_stored_data_frames(finger_off_frame, now)
        self.assertEqual(len(dps_off), 0)

    def test_commands_session_data(self):
        cmd = Commands.session_data(0x04, 0x01, 0x01)
        self.assertEqual(len(cmd), 64)
        self.assertEqual(cmd[0], 0x9D)
        self.assertEqual(cmd[1], 0x04)
        self.assertEqual(cmd[7], 0xA4)

    def test_commands_storage_helpers(self):
        cmd_init = Commands.storage_init()
        self.assertEqual(cmd_init[0], 0x9D)
        self.assertEqual(cmd_init[1], 0x02)

        cmd_block = Commands.storage_block(1, 1)
        self.assertEqual(cmd_block[0], 0x9D)
        self.assertEqual(cmd_block[1], 0x04)

        cmd_fin = Commands.storage_finalize()
        self.assertEqual(cmd_fin[0], 0x9D)
        self.assertEqual(cmd_fin[1], 0x7F)

    def test_parsers_eb_frames(self):
        report = bytes([0xEB, 0x00, 0x04, 64, 0x30, 95] + [0]*58)
        dps = Parsers.parse_eb_frames(report)
        self.assertEqual(len(dps), 1)
        self.assertEqual(dps[0].spo2, 95)

    def test_commands_set_time(self):
        dt = datetime(2026, 9, 3, 7, 41, 6)
        cmd = Commands.set_time(dt)
        self.assertEqual(len(cmd), 64)
        self.assertEqual(cmd[0], Opcode.SET_RTC)
        self.assertEqual(cmd[1], 26)
        self.assertEqual(cmd[7], 0x54)

    def test_commands_read_time(self):
        cmd = Commands.read_time()
        self.assertEqual(len(cmd), 64)
        self.assertEqual(cmd[0], Opcode.READ_RTC)

    def test_parsers_rtc_time(self):
        report = bytes([0xF2, 0x00, 0x00, 26, 9, 3, 7, 41, 6] + [0]*55)
        dt = Parsers.parse_rtc_time(report)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

    def test_parsers_serial(self):
        report_sn = bytes([0xF1, 0x35, 0x30, 0x46, 0x20, 0x20] + [0]*58)
        sn, _ = Parsers.parse_serial(report_sn)
        self.assertEqual(sn, "50F")

    def test_parsers_geometry(self):
        report = bytes([0x9E, 0x70, 0x04, 0x84] + [0]*60)
        geom = Parsers.parse_geometry(report)
        self.assertEqual(geom, "112 Bytes Sub-chunk Payload, 4 KB Address Block")


if __name__ == "__main__":
    unittest.main()
