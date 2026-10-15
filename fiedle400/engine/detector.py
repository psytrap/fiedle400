"""Serial Packet Detector for Pulsox PO-400 / CMS-60D stream reports."""

from datetime import datetime, timedelta
from typing import List, Optional, Union

from ..protocol import (
    DecodedPacket,
    SessionInfo,
    DeviceInfo,
    Parsers,
    decode_status_flags,
    unmask_subframe_msb,
)
from .buffer import SerialByteStreamBuffer


class SerialPacketDetector:
    """Signature-based packet detector and stream decoder."""
    base_val: Optional[int] = None
    pending_split: Optional[int] = None
    last_block_type: Optional[bool] = None

    @classmethod
    def reset_decoder_state(cls) -> None:
        cls.base_val = None
        cls.pending_split = None
        cls.last_block_type = None

    @classmethod
    def detect_and_decode_stream(
        cls,
        stream_buf: SerialByteStreamBuffer,
        base_timestamp: Optional[datetime] = None,
    ) -> List[DecodedPacket]:
        """Scans continuous stream buffer across HID report boundaries and returns complete DecodedPackets."""
        events: List[DecodedPacket] = []
        if base_timestamp is None:
            base_timestamp = datetime.now()

        buf = stream_buf._buffer
        last_block_id: Optional[int] = None
        last_seq: Optional[int] = None

        while len(buf) > 0:
            # 1. Check for COMMAND_ACK (0xF0 0x70)
            if len(buf) >= 2 and buf[0] == 0xF0 and buf[1] == 0x70:
                chunk = stream_buf.consume(2)
                events.append(DecodedPacket(
                    packet_type="COMMAND_ACK",
                    timestamp=base_timestamp,
                    status_str="ack_success",
                    raw_payload=bytes(chunk),
                ))
                continue

            # 2. Check for RTC Readback Response (0xF2)
            if buf[0] == 0xF2:
                if len(buf) < 10:
                    break  # Wait for remaining bytes in next report
                chunk = stream_buf.consume(10)
                dt = Parsers.parse_rtc_time(chunk)
                events.append(DecodedPacket(
                    packet_type="RTC_RESPONSE",
                    timestamp=dt or base_timestamp,
                    status_str="ok" if dt else "invalid",
                    raw_payload=bytes(chunk),
                ))
                continue

            # 3. Check for Session Index Report (0xEC)
            if buf[0] == 0xEC:
                if len(buf) < 16:
                    break  # Wait for remaining bytes in next report
                chunk = stream_buf.consume(16)
                sessions = Parsers.parse_session_index(chunk)
                for s in sessions:
                    events.append(DecodedPacket(
                        packet_type="SESSION_INDEX",
                        timestamp=s.timestamp or base_timestamp,
                        session_info=s,
                        status_str="ok",
                        raw_payload=bytes(chunk),
                    ))
                continue

            # 4. Check for Stored Download Sub-chunk (0xED 0x04)
            if buf[0] == 0xED:
                if len(buf) < 2:
                    break  # Wait for 0x04 byte in next report
                if buf[1] == 0x04:
                    if len(buf) < 30:
                        break  # Wait for full 30-byte sub-chunk stream unit
                    chunk = stream_buf.consume(30)
                    block_id = chunk[2]
                    seq      = chunk[3]
                    flags    = chunk[7]   # legacy single-sample frames only; for series frames byte 7 is mask m2

                    # Flash sentinel: block_id=0, seq=0, uninitialized flash bytes (0x7F)
                    if block_id == 0x00 and seq == 0x00 and chunk[5] == 0x7F and chunk[9] == 0x7F:
                        events.append(DecodedPacket(
                            packet_type="FLASH_SENTINEL",
                            timestamp=base_timestamp,
                            status_flags=0x7F,
                            status_str="flash-sentinel",
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            seq=seq,
                        ))
                        continue

                    # Sequence gap validation
                    sequence_gap = False
                    expected_seq = None
                    if last_block_id == block_id and last_seq is not None:
                        exp_s = last_seq + 1
                        if seq != exp_s:
                            sequence_gap = True
                            expected_seq = exp_s

                    last_block_id = block_id
                    last_seq = seq

                    # 7-bit MSB unmasking of bytes 8..28 using mask bytes 5..7
                    unmasked = unmask_subframe_msb(chunk)

                    is_spo2_block = (block_id in (1, 3, 5, 7) or block_id % 2 == 1)
                    if cls.last_block_type != is_spo2_block:
                        cls.base_val = None
                        cls.pending_split = None
                        cls.last_block_type = is_spo2_block

                    # A time-series frame carries delta-nibble data, or ends with the 0xFF 0xFF
                    # terminator that pads the short final frame of a reply. Byte 7 is the third MSB
                    # mask (PROTOCOL.md 3.5), not a status field, so it must not decide this.
                    has_series_payload = (
                        len(unmasked) > 0 and (unmasked[0] & 0xF0 == 0xF0)
                    ) or (
                        sum(1 for b in unmasked if (b & 0x7F) not in (0x00, 0x7F)) >= 4
                    ) or any(unmasked[i] == 0xFF and unmasked[i + 1] == 0xFF for i in range(len(unmasked) - 1))

                    if has_series_payload and (sum(chunk[:29]) & 0x7F) != chunk[29]:
                        # Every real stored frame ends with the 7-bit sum of its first 29 bytes
                        # (PROTOCOL.md 3.5): a mismatch means bytes were corrupted, so none are trusted.
                        events.append(DecodedPacket(
                            packet_type="CORRUPT_FRAME",
                            timestamp=base_timestamp,
                            status_str="bad-checksum",
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            seq=seq,
                            sequence_gap=sequence_gap,
                            expected_seq=expected_seq,
                        ))
                        continue

                    if not has_series_payload:
                        status_str = decode_status_flags(flags)
                        is_probe_out = bool(flags & 0x10) or (flags & 0x0F == 0x0F)
                    else:
                        flags = 0
                        status_str = "ok"
                        is_probe_out = False

                    if has_series_payload:
                        p_idx = 0
                        while p_idx < len(unmasked):
                            b = unmasked[p_idx]

                            if cls.pending_split is not None:
                                cls.base_val = cls.pending_split | (b & 0x0F)
                                cls.pending_split = None
                                p_idx += 1
                                continue

                            # Dynamic base value escape 0xF_ 0xF_
                            if (b & 0xF0) == 0xF0:
                                if p_idx == len(unmasked) - 1:
                                    cls.pending_split = (b & 0x0F) << 4
                                    p_idx += 1
                                    continue
                                b_next = unmasked[p_idx + 1]
                                if b == 0xFF and b_next == 0xFF:
                                    break
                                if (b_next & 0xF0) == 0xF0:
                                    cls.base_val = ((b & 0x0F) << 4) | (b_next & 0x0F)
                                    p_idx += 2
                                    continue

                            if cls.base_val is None:
                                cls.base_val = 98 if is_spo2_block else 60

                            h_nib = (b >> 4) & 0x0F
                            l_nib = b & 0x0F
                            v1 = cls.base_val - h_nib
                            v2 = (cls.base_val - l_nib) if (l_nib != 0x0F) else v1

                            spo2_val = None
                            hr_val = None
                            # Out-of-range readings are the stream's finger-out marker (SpO2 0x7F = 127,
                            # pulse 0xFF = 255; analysis/bum400_20260906_100516.md section 4).
                            limit = 100 if is_spo2_block else 254
                            valid = 0 < v1 <= limit and 0 < v2 <= limit
                            if valid:
                                if is_spo2_block:
                                    spo2_val = round((v1 + v2) / 2.0)
                                else:
                                    hr_val = round((v1 + v2) / 2.0)

                            events.append(DecodedPacket(
                                packet_type="STORED_BLOCK",
                                timestamp=base_timestamp + timedelta(seconds=len(events)),
                                spo2=spo2_val,
                                heart_rate=hr_val,
                                ppg_wave=0,
                                status_flags=flags,
                                status_str="ok" if valid else "probe-out",
                                raw_payload=bytes(chunk),
                                block_id=block_id,
                                seq=seq,
                                sequence_gap=sequence_gap,
                                expected_seq=expected_seq,
                                invalid_sample=not valid,
                            ))
                            p_idx += 1
                    else:
                        # Fallback for single-sample header / legacy sub-chunks
                        if seq == 0:
                            spo2_val = (chunk[5] - 18) if (48 <= chunk[5] <= 118 and not is_probe_out) else None
                            hr_val   = (chunk[9] - 56) if (81 <= chunk[9] <= 306) else None
                            ppg_wave = 0
                        else:
                            spo2_val = None
                            hr_val   = None
                            ppg_wave = (chunk[8] << 4) | (chunk[9] >> 4)

                        spo2_valid = spo2_val is not None and 30 <= spo2_val <= 100
                        hr_valid   = hr_val   is not None and 25 <= hr_val   <= 250

                        events.append(DecodedPacket(
                            packet_type="STORED_BLOCK",
                            timestamp=base_timestamp + timedelta(seconds=len(events)),
                            spo2=spo2_val if spo2_valid else None,
                            heart_rate=hr_val if hr_valid else None,
                            ppg_wave=ppg_wave,
                            status_flags=flags,
                            status_str=status_str,
                            raw_payload=bytes(chunk),
                            block_id=block_id,
                            seq=seq,
                            sequence_gap=sequence_gap,
                            expected_seq=expected_seq,
                        ))
                    continue

            # 5. Check for Live Streaming Sub-chunk (0xEB)
            if buf[0] == 0xEB:
                if len(buf) < 6:
                    break  # Sub-chunk straddles boundary
                chunk = stream_buf.consume(6)
                ppg_wave = chunk[2]
                hr = chunk[3]
                flags = chunk[4]
                spo2 = chunk[5]

                spo2_valid = 30 <= spo2 <= 100
                hr_valid = 25 <= hr <= 250
                status_str = decode_status_flags(flags)

                events.append(DecodedPacket(
                    packet_type="LIVE_STREAM",
                    timestamp=base_timestamp + timedelta(seconds=len(events)),
                    spo2=spo2 if spo2_valid else None,
                    heart_rate=hr if hr_valid else None,
                    ppg_wave=ppg_wave,
                    status_flags=flags,
                    status_str=status_str,
                    raw_payload=bytes(chunk),
                ))
                continue

            # 6. Check for Device Info Response (0x81 / 0xFE / 0xF1 / 0xF0 non-ACK)
            if buf[0] in [0x81, 0xFE, 0xF1, 0xF0]:
                if len(buf) < 16:
                    break
                chunk = stream_buf.consume(16)
                dev_info = Parsers.parse_device_info(chunk)
                if dev_info.firmware_version or dev_info.serial_number:
                    events.append(DecodedPacket(
                        packet_type="DEVICE_INFO",
                        timestamp=base_timestamp,
                        device_info=dev_info,
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # 7. Check for Serial Number / User Profile Response (0x8E)
            if buf[0] == 0x8E:
                if len(buf) < 16:
                    break
                chunk = stream_buf.consume(16)
                sn, up = Parsers.parse_serial(chunk)
                if sn or up:
                    events.append(DecodedPacket(
                        packet_type="SERIAL_PROFILE",
                        timestamp=base_timestamp,
                        device_info=DeviceInfo(serial_number=sn, user_profile=up),
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # 8. Check for Storage Architecture Geometry Response (0x9E)
            if buf[0] == 0x9E:
                if len(buf) < 16:
                    break
                chunk = stream_buf.consume(16)
                geom = Parsers.parse_geometry(chunk)
                if geom:
                    events.append(DecodedPacket(
                        packet_type="GEOMETRY_INFO",
                        timestamp=base_timestamp,
                        device_info=DeviceInfo(flash_geometry=geom),
                        raw_payload=bytes(chunk),
                    ))
                    continue

            # Skip / resynchronize: Scan forward for next candidate header byte
            next_sync_idx = -1
            for idx in range(1, len(buf)):
                b = buf[idx]
                if b == 0xED and (idx + 1 >= len(buf) or buf[idx + 1] == 0x04):
                    next_sync_idx = idx
                    break
                if b == 0xEB:
                    next_sync_idx = idx
                    break
                if b == 0xF0 and (idx + 1 >= len(buf) or buf[idx + 1] == 0x70):
                    next_sync_idx = idx
                    break
                if b in [0xF2, 0xEC, 0x81, 0xFE, 0xF1, 0x8E, 0x9E]:
                    next_sync_idx = idx
                    break

            if next_sync_idx > 0:
                stream_buf.consume(next_sync_idx)
            else:
                stream_buf.consume(1)

        return events

    @staticmethod
    def detect_and_decode(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DecodedPacket]:
        """Wrapper scanning report bytes using SerialByteStreamBuffer."""
        buf = SerialByteStreamBuffer()
        buf.write(report_bytes)
        return SerialPacketDetector.detect_and_decode_stream(buf, base_timestamp)
