import unittest
from datetime import datetime
from fiedle400.protocol import (
    Commands,
    Parsers,
    Opcode,
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

    def test_parse_30byte_ed_subframes(self):
        # Sample 30-byte 0xED 0x04 SpO2 subframe with valid 7-bit checksum:
        # ed 04 01 00 00 03 00 00 76 71 10 00 ... chk=0x7D
        # 0x76, 0x71 with m0=0x03 unmask to 0xF6 0xF1 -> Base SpO2 = 97.
        # Byte 10: 0x10 -> Delta nibbles: 97-1 = 96%, 97-0 = 97%.
        raw = bytes([0xED, 0x04, 0x01, 0x00, 0x00, 0x03, 0x00, 0x00, 0x76, 0x71, 0x10] + [0] * 18)
        chk = sum(raw[:29]) & 0x7F
        raw_full = raw[:29] + bytes([chk])
        
        pts = Parsers.parse_ed_frames(raw_full)
        self.assertGreater(len(pts), 0)
        self.assertEqual(pts[0].spo2, 96)
        self.assertEqual(pts[1].spo2, 97)

    def test_decode_usb_vid_pid(self):
        arch, src = decode_usb_vid_pid("28E9", "028A")
        self.assertIn("GigaDevice MCU HID Oximeter", arch)
        self.assertIn("SpO2.exe HID scan", src)

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

    def test_parsers_ec_session_index(self):
        # 0xEC report for Session #2: header count 204 = 204 samples, one per second (3m 24s; T-075)
        report_ec = bytes([0xEC, 0x00, 0x01, 0x02, 26, 9, 4, 21, 46, 47, 76, 1, 0, 0, 117, 115, 101, 114, 0, 0, 0] + [0]*43)
        sessions = Parsers.parse_session_index(report_ec)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, 2)
        self.assertEqual(sessions[0].user_id, 1)
        self.assertEqual(sessions[0].duration_sec, 204)
        self.assertEqual(sessions[0].duration_str, "3m 24s")
        self.assertEqual(sessions[0].record_count, 204)
        self.assertEqual(sessions[0].raw_samples, 204)

    def test_parsers_ec_odd_sample_count_is_seconds_too(self):
        report_ec = bytes([0xEC, 0x00, 0x01, 0x01, 26, 9, 4, 21, 46, 47, 115, 1, 0, 0] + [0]*50)   # 243 samples
        (s,) = Parsers.parse_session_index(report_ec)
        self.assertEqual((s.raw_samples, s.record_count, s.duration_sec), (243, 243, 243))

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
        self.assertEqual(cmd[2], 0x01)
        self.assertEqual(cmd[3], 0x01)
        self.assertEqual(cmd[4], 0x01)
        self.assertEqual(cmd[8], (0x04 + 0x01 + 0x01 + 0x01 + 0x1D) & 0xFF)


    def test_commands_storage_helpers(self):
        cmd_init = Commands.storage_init()
        self.assertEqual(len(cmd_init), 64)
        self.assertEqual(cmd_init[0], 0x9D)
        self.assertEqual(cmd_init[1], 0x02)

        cmd_block = Commands.storage_block(1, 1)
        self.assertEqual(len(cmd_block), 64)
        self.assertEqual(cmd_block[0], 0x9D)
        self.assertEqual(cmd_block[1], 0x04)
        self.assertEqual(cmd_block[2], 0x01)

        cmd_fin = Commands.storage_finalize()
        self.assertEqual(len(cmd_fin), 64)
        self.assertEqual(cmd_fin[0], 0x9D)
        self.assertEqual(cmd_fin[1], 0x7F)



    def test_parsers_eb_frames(self):
        report = bytes([0xEB, 0x00, 0x04, 48, 64, 95] + [0]*58)
        dps = Parsers.parse_eb_frames(report)
        self.assertEqual(len(dps), 1)
        self.assertEqual(dps[0].spo2, 95)
        self.assertEqual(dps[0].heart_rate, 48)
        self.assertEqual(dps[0].ppg_wave, 4)
        self.assertEqual(dps[0].status_flags, 64)

    def test_parsers_ed_frames(self):
        report = bytes([0xED, 0x00, 0x04, 48, 64, 95] + [0]*58)
        dps = Parsers.parse_ed_frames(report)
        self.assertEqual(len(dps), 1)
        self.assertEqual(dps[0].spo2, 95)
        self.assertEqual(dps[0].heart_rate, 48)
        self.assertEqual(dps[0].ppg_wave, 4)
        self.assertEqual(dps[0].status_flags, 64)


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

    def test_parsers_serial(self):
        report_sn = bytes([0xF1, 0x35, 0x30, 0x46, 0x20, 0x20] + [0]*58)
        sn, _ = Parsers.parse_serial(report_sn)
        self.assertEqual(sn, "50F")

    def test_parsers_geometry(self):
        report = bytes([0x9E, 0x70, 0x04, 0x84] + [0]*60)
        geom = Parsers.parse_geometry(report)
        self.assertEqual(geom, "112 Bytes Sub-chunk Payload, 4 KB Address Block")


    def test_session_info_duration_str(self):
        s1 = SessionInfo(session_id=1, user_id=1, record_count=2564)
        self.assertEqual(s1.duration_seconds, 2564)
        self.assertEqual(s1.duration_str, "42m 44s")

        s2 = SessionInfo(session_id=2, user_id=1, record_count=13056)
        self.assertEqual(s2.duration_str, "3h 37m 36s")

        s3 = SessionInfo(session_id=3, user_id=1, record_count=45)
        self.assertEqual(s3.duration_str, "45s")

        s_zero = SessionInfo(session_id=0, user_id=1, record_count=0)
        self.assertEqual(s_zero.duration_str, "0s")

    def test_parsers_stored_download_block(self):
        # 0xED 0x04 report: Byte 5 = 115 (SpO2 = 115 - 18 = 97%), Byte 9 = 114 (HR = 114 - 56 = 58)
        report = bytes([0xED, 0x04, 0x01, 0, 0, 115, 0, 0x00, 0, 114] + [0]*54)
        dps = Parsers.parse_stored_block(report)
        self.assertEqual(len(dps), 1)
        self.assertEqual(dps[0].spo2, 97)
        self.assertEqual(dps[0].heart_rate, 58)
        self.assertEqual(dps[0].status_flags, 0x00)

        # Test out-of-bounds invalid block
        invalid_report = bytes([0xED, 0x04, 0x01, 0, 0, 1, 0, 0x00, 10, 10] + [0]*54)
        dps_invalid = Parsers.parse_stored_block(invalid_report)
        self.assertEqual(len(dps_invalid), 0)

    def test_decode_ed_subframes_real_hardware_payload(self):
        sf0 = bytes.fromhex("ed040100000300007672333322222333332333333333333322223222211e")
        sf_term = bytes.fromhex("ed04010500707f7f000000007f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f54")
        samples = Parsers.decode_ed_subframes([sf0, sf_term], is_spo2=True)
        # sf0 has 19 data bytes (each 2 samples = 38 samples) + sf_term has 4 data bytes (8 samples) = 46 samples
        self.assertEqual(len(samples), 46)
        # Verify plausible physiological SpO2 values
        self.assertTrue(all(94 <= s <= 98 for s in samples))


if __name__ == "__main__":
    unittest.main()
