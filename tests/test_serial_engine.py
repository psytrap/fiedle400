import unittest
from datetime import datetime
from fiedle400.serial_engine import (
    SerialByteStreamBuffer,
    SerialPacketDetector,
    DecodedPacket,
)


class TestSerialEngine(unittest.TestCase):

    def test_byte_stream_buffer(self):
        buf = SerialByteStreamBuffer(max_capacity=100)
        self.assertEqual(len(buf), 0)

        buf.write(b"\x01\x02\x03\x04")
        self.assertEqual(len(buf), 4)
        self.assertEqual(buf.peek(2), b"\x01\x02")

        chunk = buf.consume(2)
        self.assertEqual(chunk, b"\x01\x02")
        self.assertEqual(len(buf), 2)
        self.assertEqual(buf.peek(2), b"\x03\x04")

        buf.clear()
        self.assertEqual(len(buf), 0)

    def test_packet_detector_ack(self):
        ack_report = bytes([0xF0, 0x70] + [0] * 62)
        events = SerialPacketDetector.detect_and_decode(ack_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "COMMAND_ACK")
        self.assertEqual(events[0].status_str, "ack_success")

    def test_packet_detector_stored_block_header(self):
        # Block header sub-chunk (seq=0, block_id=1):
        # c[5]=0x73=115 → SpO2=115-18=97, c[9]=0x79=121 → HR=121-56=65, flags=0x00
        stored_report = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x73, 0, 0x00, 0x00, 0x79] + [0] * 54)
        events = SerialPacketDetector.detect_and_decode(stored_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "STORED_BLOCK")
        self.assertEqual(events[0].spo2, 97)
        self.assertEqual(events[0].heart_rate, 65)
        self.assertEqual(events[0].status_flags, 0x00)

    def test_packet_detector_stored_block_ppg_sample(self):
        # PPG sample sub-chunk (seq=1, block_id=1): SpO2 and HR must be None
        ppg_report = bytes([0xED, 0x04, 0x01, 0x01, 0, 0x00, 0, 0x00, 0x11, 0x11] + [0] * 54)
        events = SerialPacketDetector.detect_and_decode(ppg_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "STORED_BLOCK")
        self.assertIsNone(events[0].spo2)
        self.assertIsNone(events[0].heart_rate)
        self.assertEqual(events[0].status_flags, 0x00)

    def test_packet_detector_flash_sentinel(self):
        # Flash sentinel: block_id=0, seq=0, all 0x7F bytes
        sentinel_report = bytes([0xED, 0x04, 0x00, 0x00, 0, 0x7F, 0x7F, 0x7F, 0x7F, 0x7F] + [0] * 54)
        events = SerialPacketDetector.detect_and_decode(sentinel_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "FLASH_SENTINEL")

    def test_packet_detector_block0_high_sequence_not_sentinel(self):
        # Sub-chunk in Block 0 with seq=0x42 (66) and valid payload must be STORED_BLOCK, not FLASH_SENTINEL
        block0_seq66_report = bytes([0xED, 0x04, 0x00, 0x42, 0, 0x00, 0, 0x5F, 0x11, 0x22] + [0] * 54)
        events = SerialPacketDetector.detect_and_decode(block0_seq66_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "STORED_BLOCK")
        self.assertEqual(events[0].block_id, 0)
        self.assertEqual(events[0].seq, 0x42)

    def test_packet_detector_live_stream(self):
        live_report = bytes([0xEB, 0x00, 0x04, 64, 0x00, 96] + [0] * 58)
        events = SerialPacketDetector.detect_and_decode(live_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "LIVE_STREAM")
        self.assertEqual(events[0].spo2, 96)
        self.assertEqual(events[0].heart_rate, 64)
        self.assertEqual(events[0].ppg_wave, 4)
        self.assertEqual(events[0].status_flags, 0x00)

    def test_packet_detector_device_info(self):
        # 0x81 firmware version report: [0x81, 2, 0, 1] -> v2.0.1
        fw_report = bytes([0x81, 2, 0, 1] + [0] * 60)
        events = SerialPacketDetector.detect_and_decode(fw_report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "DEVICE_INFO")
        self.assertEqual(events[0].device_info.firmware_version, "v2.0.1")

    def test_read_device_info_engine(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xF0, 0x70, 0x01] + [0] * 61), # unlock negotiation ACK
            bytes([0xF2, 0, 0, 2, 7, 1, 12, 7, 0] + [0] * 55), # RTC clock 2002-07-01 12:07:00
            bytes([0xF0, 0xAD, 2, 0, 0] + [0] * 59), # AD info
            bytes([0x81, 2, 0, 0] + [0] * 60), # 0x81 firmware v2.0.0
            bytes([0x8E, 0x53, 0x4E, 0x31, 0x32, 0x33, 0x00] + [0] * 57), # 0x8E serial/profile
            bytes([0x8E, 0x53, 0x4E, 0x31, 0x32, 0x33, 0x00] + [0] * 57),
            bytes([0x8E, 0x53, 0x4E, 0x31, 0x32, 0x33, 0x00] + [0] * 57),
            bytes([0x9E, 0x40, 0x04] + [0] * 61), # 0x9E geometry
        ])
        engine = SerialDeviceEngine(mock_dev)
        res = engine.read_device_info()
        self.assertIn("device_info", res)
        self.assertEqual(res["active_user_id"], 1)
        self.assertEqual(res["rtc_time_str"], "2002-07-01 12:07:00")
        self.assertEqual(res["device_info"].firmware_version, "v2.0.0")

    def test_list_sessions_engine(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xF0, 0x70, 0x01] + [0] * 61), # unlock ACK
            None,
            bytes([0xF0, 0x70, 0x00] + [0] * 61), # reset index ACK
            None,
            bytes([0xEC, 0x00, 0x01, 0x01, 26, 9, 5, 14, 0, 0, 10, 0] + [0] * 52), # session 1 (10s)
            bytes([0xEC, 0x40, 0x01, 0x02, 26, 9, 5, 14, 10, 0, 5, 0] + [0] * 52), # session 2 (5s, end flag 0x40)
        ])
        engine = SerialDeviceEngine(mock_dev)
        sessions = engine.list_sessions()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].session_id, 1)
        self.assertEqual(sessions[1].session_id, 2)

    def test_read_rtc_time_engine(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xF2, 0, 0, 26, 9, 5, 14, 25, 0] + [0] * 55),
        ])
        engine = SerialDeviceEngine(mock_dev)
        dt = engine.read_rtc_time()
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 5)

    def test_unlock_handshake_engine(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xF0, 0x70, 0x02] + [0] * 61),
        ])
        engine = SerialDeviceEngine(mock_dev)
        user_id = engine.unlock_handshake()
        self.assertEqual(user_id, 2)

    def test_clear_memory_engine_mock(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xF0, 0x70] + [0] * 62),
        ])
        engine = SerialDeviceEngine(mock_dev)
        res = engine.clear_memory(session_id=1)
        self.assertTrue(res)

    def test_boundary_straddling_subchunks(self):
        buf = SerialByteStreamBuffer()
        # Part 1: Tail end of HID report contains first 3 bytes of 0xED 0x04 sub-chunk
        buf.write(bytes([0x7F, 0x7F, 0xED]))
        events1 = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual(len(events1), 0)
        self.assertEqual(len(buf), 1)  # Noise bytes 0x7F 0x7F consumed; 0xED retained!

        # Part 2: Head of next HID report completes the 30-byte 0xED 0x04 sub-chunk
        # block_id=1, seq=0 (block header): c[5]=0x73=115 → SpO2=97, c[9]=0x79=121 → HR=65
        buf.write(bytes([0x04, 0x01, 0x00, 0, 0x73, 0, 0x00, 0x00, 0x79] + [0] * 20))
        events2 = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0].packet_type, "STORED_BLOCK")
        self.assertEqual(events2[0].spo2, 97)
        self.assertEqual(events2[0].heart_rate, 65)


    def test_wait_for_10_eb_messages(self):
        from fiedle400.serial_engine import SerialDeviceEngine
        mock_dev = MockHidDevice(responses=[
            bytes([0xEB, 0x00, 0x04, 64, 0x00, 96] + [0] * 58) for _ in range(15)
        ])
        engine = SerialDeviceEngine(mock_dev)
        eb_count = engine.wait_for_eb_stream(target_count=10, max_timeout=2.0)
        self.assertEqual(eb_count, 10)

    def test_protocol_frame_lengths(self):
        buf = SerialByteStreamBuffer()
        # 30-byte 0xED 0x04 stream unit (c[5]=108 -> 108-18=90 SpO2, c[9]=114 -> 114-56=58 HR)
        ed_frame = bytes([0xED, 0x04, 0x01, 0, 0, 108, 0, 0x00, 0, 114] + [0] * 20)
        # 6-byte 0xEB frame
        eb_frame = bytes([0xEB, 0x00, 0x04, 64, 0x00, 96])
        buf.write(ed_frame + eb_frame)

        events = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].packet_type, "STORED_BLOCK")
        self.assertEqual(events[0].spo2, 90)
        self.assertEqual(events[1].packet_type, "LIVE_STREAM")
        self.assertEqual(events[1].spo2, 96)
        self.assertEqual(len(buf), 0)

    def test_forward_resynchronization_scanner(self):
        buf = SerialByteStreamBuffer()
        # Write 5 junk bytes followed by a valid 30-byte 0xED 0x04 stream unit
        junk = bytes([0x12, 0x34, 0x56, 0x78, 0x90])
        # seq=0, block_id=1: c[5]=118 -> SpO2=100%, c[9]=114 -> HR=58
        ed_frame = bytes([0xED, 0x04, 0x01, 0, 0, 118, 0, 0x00, 0, 114] + [0] * 20)
        buf.write(junk + ed_frame)

        events = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].packet_type, "STORED_BLOCK")
        self.assertEqual(events[0].spo2, 100)
        self.assertEqual(len(buf), 0)

    def test_download_session_terminates_on_flash_sentinel(self):
        """A FLASH_SENTINEL packet (block_id=0) must terminate the session download cleanly."""
        from fiedle400.serial_engine import SerialDeviceEngine
        from fiedle400.protocol import SessionInfo

        eb_frame     = bytes([0xEB, 0x00, 0x04, 64, 0x00, 96] + [0] * 58)
        unlock_ack   = bytes([0xF0, 0x70, 0x01] + [0] * 61)
        init_ack     = bytes([0xF0, 0x70, 0x01] + [0] * 61)
        # Valid block-header: block_id=1, seq=0, c[5]=0x73=97 SpO2, c[9]=0x79=65 HR
        valid_frame  = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x73, 0, 0x00, 0, 0x79] + [0] * 20)
        # Flash sentinel: block_id=0
        sentinel_frame = bytes([0xED, 0x04, 0x00, 0x00, 0, 0x7F, 0x7F, 0x7F, 0x7F, 0x7F] + [0] * 20)

        responses = [eb_frame] * 10 + [None, unlock_ack, None, init_ack, None, valid_frame, sentinel_frame]

        mock_dev = MockHidDevice(responses=responses)
        engine   = SerialDeviceEngine(mock_dev)

        # Request 5 records, but sentinel comes after 1 — download must stop at 1 record
        sess_info = SessionInfo(session_id=1, user_id=1, record_count=5, duration_sec=5)
        records   = engine.download_session(sess_info, debug=0)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["spo2"], 97)
        self.assertEqual(records[0]["heart_rate"], 65)

    def test_download_session_preserves_probe_out_and_valid_blocks(self):
        """Probe-out records are preserved with status flags; session continues without dropping records."""
        from fiedle400.serial_engine import SerialDeviceEngine
        from fiedle400.protocol import SessionInfo

        eb_frame   = bytes([0xEB, 0x00, 0x04, 64, 0x00, 96] + [0] * 58)
        unlock_ack = bytes([0xF0, 0x70, 0x01] + [0] * 61)
        init_ack   = bytes([0xF0, 0x70, 0x01] + [0] * 61)

        # Block 1: block-header (seq=0) with probe-out flag (0x0F)
        # Block 2: block-header (seq=0) with valid SpO2=97, HR=65
        dummy_header = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x0F, 0, 0x0F, 0, 0x79] + [0] * 20)
        valid_header = bytes([0xED, 0x04, 0x02, 0x00, 0, 0x73, 0, 0x00, 0, 0x79] + [0] * 20)

        responses = [eb_frame] * 10 + [None, unlock_ack, None, init_ack, None, dummy_header, None, valid_header]

        mock_dev = MockHidDevice(responses=responses)
        engine   = SerialDeviceEngine(mock_dev)

        sess_info = SessionInfo(session_id=1, user_id=1, record_count=2, duration_sec=2)
        records   = engine.download_session(sess_info, debug=0)

        self.assertEqual(len(records), 2)
        self.assertIsNone(records[0]["spo2"])
        self.assertEqual(records[1]["spo2"], 97)
        self.assertEqual(records[1]["heart_rate"], 65)

    def test_sequence_gap_detection(self):
        """Sequential sub-chunks (0, 1, 2) produce no gap; jumping to 5 flags sequence_gap=True."""
        chunk0 = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x00, 0, 0x00, 0x73, 0x79] + [0] * 20)
        chunk1 = bytes([0xED, 0x04, 0x01, 0x01, 0, 0x00, 0, 0x00, 0x11, 0x11] + [0] * 20)
        chunk2 = bytes([0xED, 0x04, 0x01, 0x02, 0, 0x00, 0, 0x00, 0x22, 0x22] + [0] * 20)
        chunk5 = bytes([0xED, 0x04, 0x01, 0x05, 0, 0x00, 0, 0x00, 0x55, 0x55] + [0] * 20)

        buf = SerialByteStreamBuffer()
        buf.write(chunk0 + chunk1 + chunk2 + chunk5)

        events = SerialPacketDetector.detect_and_decode_stream(buf)
        self.assertEqual(len(events), 4)

        self.assertFalse(events[0].sequence_gap)
        self.assertFalse(events[1].sequence_gap)
        self.assertFalse(events[2].sequence_gap)

        self.assertTrue(events[3].sequence_gap)
        self.assertEqual(events[3].expected_seq, 3)
        self.assertEqual(events[3].seq, 5)

    def test_download_session_multipage_and_no_ppg_wave(self):
        """Verify multi-page iteration across Page 0 and Page 1 and absence of ppg_wave in records."""
        from fiedle400.serial_engine import SerialDeviceEngine
        from fiedle400.protocol import SessionInfo

        eb_frame   = bytes([0xEB, 0x00, 0x04, 64, 0x00, 96] + [0] * 58)
        unlock_ack = bytes([0xF0, 0x70, 0x01] + [0] * 61)
        init_ack   = bytes([0xF0, 0x70, 0x01] + [0] * 61)

        # Page 0: SpO2 frame + Pulse frame
        p0_s = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x73, 0, 0x00, 0, 0x79] + [0] * 20)
        # Page 1: SpO2 frame
        p1_s = bytes([0xED, 0x04, 0x01, 0x00, 0, 0x74, 0, 0x00, 0, 0x7A] + [0] * 20)

        responses = [eb_frame] * 10 + [None, unlock_ack, None, init_ack, None, p0_s, None, p1_s]
        mock_dev = MockHidDevice(responses=responses)
        engine   = SerialDeviceEngine(mock_dev)

        sess_info = SessionInfo(session_id=1, user_id=1, record_count=2, duration_sec=2)
        records   = engine.download_session(sess_info, debug=0)

        self.assertEqual(len(records), 2)
        for r in records:
            self.assertNotIn("ppg_wave", r)
        self.assertEqual(records[0]["spo2"], 97)
        self.assertEqual(records[1]["spo2"], 98)


class MockHidDevice:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.written = []

    def write_report(self, data):
        self.written.append(data)

    def read_report(self, size=64):
        if self.responses:
            return self.responses.pop(0)
        return None

    def close(self):
        pass


if __name__ == "__main__":
    unittest.main()

