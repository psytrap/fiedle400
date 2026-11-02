"""Serial Packet Detector for Pulsox PO-400 / CMS-60D stream reports."""

from datetime import datetime, timedelta
from typing import List, Optional

from ..protocol import (
    DecodedPacket,
    DeviceInfo,
    Parsers,
    decode_status_flags,
    unmask_subframe_msb,
)
from .buffer import SerialByteStreamBuffer


class SerialPacketDetector:
    """Signature-based packet detector and stream decoder."""
    base_value: Optional[int] = None
    pending_split: Optional[int] = None
    last_block_type: Optional[bool] = None

    @classmethod
    def reset_decoder_state(cls) -> None:
        cls.base_value = None
        cls.pending_split = None
        cls.last_block_type = None

    @classmethod
    def detect_and_decode_stream(
        cls,
        stream_buffer: SerialByteStreamBuffer,
        base_timestamp: Optional[datetime] = None,
    ) -> List[DecodedPacket]:
        """Scans continuous stream buffer across HID report boundaries and returns complete DecodedPackets."""
        events: List[DecodedPacket] = []
        if base_timestamp is None:
            base_timestamp = datetime.now()

        buffer = stream_buffer._buffer
        last_block_id: Optional[int] = None
        last_sequence: Optional[int] = None

        while len(buffer) > 0:
            # 1. Check for COMMAND_ACK (0xF0 0x70)
            if len(buffer) >= 2 and buffer[0] == 0xF0 and buffer[1] == 0x70:
                chunk = stream_buffer.consume(2)
                events.append(DecodedPacket(
                    packet_type="COMMAND_ACK",
                    timestamp=base_timestamp,
                    status_text="ack_success",
                    raw_payload=bytes(chunk),
                ))
                continue

            # 2. Check for the clock reply (0xF2). 8 bytes, the last is the checksum.
            # Every recording shows the same bytes (PROTOCOL.md §3.3), so no time is decoded.
            if buffer[0] == 0xF2:
                if len(buffer) < 8:
                    break  # Wait for remaining bytes in next report
                chunk = stream_buffer.consume(8)
                events.append(DecodedPacket(
                    packet_type="RTC_RESPONSE",
                    timestamp=base_timestamp,
                    status_text="ok",
                    raw_payload=bytes(chunk),
                ))
                continue

            # 3. Check for Session Index Report (0xEC)
            if buffer[0] == 0xEC:
                if len(buffer) < 16:
                    break  # Wait for remaining bytes in next report
                chunk = stream_buffer.consume(16)
                sessions = Parsers.parse_session_index(chunk)
                for session in sessions:
                    events.append(DecodedPacket(
                        packet_type="SESSION_INDEX",
                        timestamp=session.timestamp or base_timestamp,
                        session_info=session,
                        status_text="ok",
                        raw_payload=bytes(chunk),
                    ))
                continue

            # 4. Check for Stored Download Sub-chunk (0xED 0x04)
            if buffer[0] == 0xED:
                if len(buffer) < 2:
                    break  # Wait for 0x04 byte in next report
                if buffer[1] == 0x04:
                    if len(buffer) < 30:
                        break  # Wait for full 30-byte sub-chunk stream unit
                    chunk = stream_buffer.consume(30)
                    block_id = chunk[2]
                    sequence      = chunk[3]
                    flags    = chunk[7]   # legacy single-sample frames only; for series frames byte 7 is mask m2

                    # Flash sentinel: block_id=0, seq=0, uninitialized flash bytes (0x7F)
                    if block_id == 0x00 and sequence == 0x00 and chunk[5] == 0x7F and chunk[9] == 0x7F:
                        events.append(DecodedPacket(
                            packet_type="FLASH_SENTINEL",
                            timestamp=base_timestamp,
                            status_flags=0x7F,
                            status_text="flash-sentinel",
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            sequence=sequence,
                        ))
                        continue

                    # Sequence gap validation
                    sequence_gap = False
                    expected_sequence = None
                    if last_block_id == block_id and last_sequence is not None:
                        expected_next_sequence = last_sequence + 1
                        if sequence != expected_next_sequence:
                            sequence_gap = True
                            expected_sequence = expected_next_sequence

                    last_block_id = block_id
                    last_sequence = sequence

                    # 7-bit MSB unmasking of bytes 8..28 using mask bytes 5..7
                    unmasked = unmask_subframe_msb(chunk)

                    is_spo2_block = (block_id in (1, 3, 5, 7) or block_id % 2 == 1)
                    if cls.last_block_type != is_spo2_block:
                        cls.base_value = None
                        cls.pending_split = None
                        cls.last_block_type = is_spo2_block

                    # A time-series frame carries delta-nibble data, or ends with the 0xFF 0xFF
                    # terminator that pads the short final frame of a reply. Byte 7 is the third MSB
                    # mask (PROTOCOL.md 3.5), not a status field, so it must not decide this.
                    has_series_payload = (
                        len(unmasked) > 0 and (unmasked[0] & 0xF0 == 0xF0)
                    ) or (
                        sum(1 for byte in unmasked if (byte & 0x7F) not in (0x00, 0x7F)) >= 4
                    ) or any(unmasked[i] == 0xFF and unmasked[i + 1] == 0xFF for i in range(len(unmasked) - 1))

                    if has_series_payload and (sum(chunk[:29]) & 0x7F) != chunk[29]:
                        # Every real stored frame ends with the 7-bit sum of its first 29 bytes
                        # (PROTOCOL.md 3.5): a mismatch means bytes were corrupted, so none are trusted.
                        events.append(DecodedPacket(
                            packet_type="CORRUPT_FRAME",
                            timestamp=base_timestamp,
                            status_text="bad-checksum",
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            sequence=sequence,
                            sequence_gap=sequence_gap,
                            expected_sequence=expected_sequence,
                        ))
                        continue

                    if not has_series_payload:
                        status_text = decode_status_flags(flags)
                        is_probe_out = bool(flags & 0x10) or (flags & 0x0F == 0x0F)
                    else:
                        flags = 0
                        status_text = "ok"
                        is_probe_out = False

                    if has_series_payload:
                        position = 0
                        while position < len(unmasked):
                            byte = unmasked[position]

                            if cls.pending_split is not None:
                                cls.base_value = cls.pending_split | (byte & 0x0F)
                                cls.pending_split = None
                                position += 1
                                continue

                            # Dynamic base value escape 0xF_ 0xF_
                            if (byte & 0xF0) == 0xF0:
                                if position == len(unmasked) - 1:
                                    cls.pending_split = (byte & 0x0F) << 4
                                    position += 1
                                    continue
                                next_byte = unmasked[position + 1]
                                if byte == 0xFF and next_byte == 0xFF:
                                    break
                                if (next_byte & 0xF0) == 0xF0:
                                    cls.base_value = ((byte & 0x0F) << 4) | (next_byte & 0x0F)
                                    position += 2
                                    continue

                            if cls.base_value is None:
                                cls.base_value = 98 if is_spo2_block else 60

                            # One sample per nibble, as SpO2.exe's decoder (0x4e9b49) does: base minus
                            # the high nibble, then base minus the low nibble unless it is the 0xF
                            # filler of a frame's last byte. One sample is one second (T-075).
                            high_nibble = (byte >> 4) & 0x0F
                            low_nibble = byte & 0x0F
                            values = [cls.base_value - high_nibble] + ([cls.base_value - low_nibble] if low_nibble != 0x0F else [])

                            # Out-of-range readings are the stream's finger-out marker (SpO2 0x7F = 127,
                            # pulse 0xFF = 255; analysis/bum400_20260906_100516.md section 4).
                            limit = 100 if is_spo2_block else 254
                            for value in values:
                                valid = 0 < value <= limit
                                events.append(DecodedPacket(
                                    packet_type="STORED_BLOCK",
                                    timestamp=base_timestamp + timedelta(seconds=len(events)),
                                    spo2=value if valid and is_spo2_block else None,
                                    heart_rate=value if valid and not is_spo2_block else None,
                                    ppg_wave=0,
                                    status_flags=flags,
                                    status_text="ok" if valid else "probe-out",
                                    raw_payload=bytes(chunk),
                                    block_id=block_id,
                                    sequence=sequence,
                                    sequence_gap=sequence_gap,
                                    expected_sequence=expected_sequence,
                                    invalid_sample=not valid,
                                ))
                            position += 1
                    else:
                        # Fallback for single-sample header / legacy sub-chunks
                        if sequence == 0:
                            spo2_value = (chunk[5] - 18) if (48 <= chunk[5] <= 118 and not is_probe_out) else None
                            heart_rate_value   = (chunk[9] - 56) if (81 <= chunk[9] <= 306) else None
                            ppg_wave = 0
                        else:
                            spo2_value = None
                            heart_rate_value   = None
                            ppg_wave = (chunk[8] << 4) | (chunk[9] >> 4)

                        spo2_valid = spo2_value is not None and 30 <= spo2_value <= 100
                        heart_rate_valid   = heart_rate_value   is not None and 25 <= heart_rate_value   <= 250

                        events.append(DecodedPacket(
                            packet_type="STORED_BLOCK",
                            timestamp=base_timestamp + timedelta(seconds=len(events)),
                            spo2=spo2_value if spo2_valid else None,
                            heart_rate=heart_rate_value if heart_rate_valid else None,
                            ppg_wave=ppg_wave,
                            status_flags=flags,
                            status_text=status_text,
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            sequence=sequence,
                            sequence_gap=sequence_gap,
                            expected_sequence=expected_sequence,
                        ))
                    continue

            # 5. Check for Live Streaming Sub-chunk (0xEB)
            if buffer[0] == 0xEB:
                if len(buffer) < 6:
                    break  # Sub-chunk straddles boundary
                chunk = stream_buffer.consume(6)
                ppg_wave = chunk[2]
                heart_rate = chunk[3]
                flags = chunk[4]
                spo2 = chunk[5]

                spo2_valid = 30 <= spo2 <= 100
                heart_rate_valid = 25 <= heart_rate <= 250
                status_text = decode_status_flags(flags)

                events.append(DecodedPacket(
                    packet_type="LIVE_STREAM",
                    timestamp=base_timestamp + timedelta(seconds=len(events)),
                    spo2=spo2 if spo2_valid else None,
                    heart_rate=heart_rate if heart_rate_valid else None,
                    ppg_wave=ppg_wave,
                    status_flags=flags,
                    status_text=status_text,
                    raw_payload=bytes(chunk),
                ))
                continue

            # 6. Check for Device Info Response (0x81 / 0xFE / 0xF1 / 0xF0 non-ACK)
            if buffer[0] in [0x81, 0xFE, 0xF1, 0xF0]:
                if len(buffer) < 16:
                    break
                chunk = stream_buffer.consume(16)
                device_info = Parsers.parse_device_info(chunk)
                if device_info.firmware_version or device_info.serial_number:
                    events.append(DecodedPacket(
                        packet_type="DEVICE_INFO",
                        timestamp=base_timestamp,
                        device_info=device_info,
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # 7. Check for Serial Number / User Profile Response (0x8E)
            if buffer[0] == 0x8E:
                if len(buffer) < 16:
                    break
                chunk = stream_buffer.consume(16)
                serial_number, user_profile = Parsers.parse_serial(chunk)
                if serial_number or user_profile:
                    events.append(DecodedPacket(
                        packet_type="SERIAL_PROFILE",
                        timestamp=base_timestamp,
                        device_info=DeviceInfo(serial_number=serial_number, user_profile=user_profile),
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # 8. Check for Storage Architecture Geometry Response (0x9E)
            if buffer[0] == 0x9E:
                if len(buffer) < 16:
                    break
                chunk = stream_buffer.consume(16)
                geometry = Parsers.parse_geometry(chunk)
                if geometry:
                    events.append(DecodedPacket(
                        packet_type="GEOMETRY_INFO",
                        timestamp=base_timestamp,
                        device_info=DeviceInfo(flash_geometry=geometry),
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # Skip / resynchronize: Scan forward for next candidate header byte
            next_sync_index = -1
            for index in range(1, len(buffer)):
                byte = buffer[index]
                if byte == 0xED and (index + 1 >= len(buffer) or buffer[index + 1] == 0x04):
                    next_sync_index = index
                    break
                if byte == 0xEB:
                    next_sync_index = index
                    break
                if byte == 0xF0 and (index + 1 >= len(buffer) or buffer[index + 1] == 0x70):
                    next_sync_index = index
                    break
                if byte in [0xF2, 0xEC, 0x81, 0xFE, 0xF1, 0x8E, 0x9E]:
                    next_sync_index = index
                    break

            if next_sync_index > 0:
                stream_buffer.consume(next_sync_index)
            else:
                stream_buffer.consume(1)

        return events

    @staticmethod
    def detect_and_decode(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DecodedPacket]:
        """Wrapper scanning report bytes using SerialByteStreamBuffer."""
        buffer = SerialByteStreamBuffer()
        buffer.write(report_bytes)
        return SerialPacketDetector.detect_and_decode_stream(buffer, base_timestamp)
