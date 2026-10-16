"""Inbound HID report decoders and Parsers factory class."""

from datetime import datetime
from typing import List, Optional, Tuple

from .models import DataPoint, SessionInfo, DeviceInfo
from .decompression import decode_ed_subframes


def parse_segment_metadata(report_bytes: bytes) -> Optional[Tuple[datetime, str]]:
    """Parses 0xEC segment index report for session start time and user name."""
    if len(report_bytes) >= 16 and report_bytes[0] == 0xEC:
        yr = 2000 + report_bytes[4] if report_bytes[4] < 100 else 2026
        mo = max(1, min(12, report_bytes[5]))
        dy = max(1, min(31, report_bytes[6]))
        hr = min(23, report_bytes[7])
        mi = min(59, report_bytes[8])
        sc = min(59, report_bytes[9])
        
        user_name = "user"
        if len(report_bytes) >= 20:
            raw_name = report_bytes[15:25].decode("ascii", errors="ignore").strip()
            if raw_name:
                user_name = raw_name
                
        try:
            return datetime(yr, mo, dy, hr, mi, sc), user_name
        except Exception:
            return None, user_name
    return None


def parse_serial_response(report_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
    """Parses 0xFE / 0xF1 device info input report to extract (serial_number, user_profile)."""
    serial_no, user_prof = None, None
    if len(report_bytes) >= 12:
        if report_bytes[0] == 0xF1:
            raw_str = report_bytes[1:12].decode("ascii", errors="ignore").strip()
            clean = "".join(c for c in raw_str if c.isalnum() or c in "-_")
            if clean:
                serial_no = clean
        elif report_bytes[0] == 0xFE:
            raw_str = report_bytes[5:15].decode("ascii", errors="ignore").strip() if len(report_bytes) >= 15 else report_bytes[1:12].decode("ascii", errors="ignore").strip()
            clean = "".join(c for c in raw_str if c.isalnum() or c in "-_ ")
            if clean:
                user_prof = clean.strip()
    return serial_no, user_prof


def parse_storage_architecture_response(report_bytes: bytes) -> Optional[str]:
    """Parses 0x9E / 0x9F Flash storage architecture report into payload and block size string."""
    if len(report_bytes) >= 4 and report_bytes[0] in [0x9E, 0x9F]:   # not 0xF0: a bare ACK (f0 70) is no geometry
        chunk_size = report_bytes[1]
        block_factor = report_bytes[2]
        if chunk_size > 0:
            if block_factor > 0:
                return f"{chunk_size} Bytes Sub-chunk Payload, {block_factor} KB Address Block"
            return f"{chunk_size} Bytes Sub-chunk Payload"
    return None


def parse_device_info(report_bytes: bytes) -> DeviceInfo:
    """Parses device info reports (0xAD, 0x81, 0x8E, 0xF1) into structured DeviceInfo object."""
    info = DeviceInfo()
    if len(report_bytes) >= 5 and report_bytes[0] in [0xF0, 0x81, 0xFE, 0xF1]:
        if report_bytes[0] == 0x81 and len(report_bytes) >= 4:
            v_maj = report_bytes[1]
            v_min = report_bytes[2]
            v_pch = report_bytes[3]
            if v_maj > 0 or v_min > 0 or v_pch > 0:
                info.firmware_version = f"v{v_maj}.{v_min}.{v_pch}"
        elif report_bytes[0] == 0xF0:
            v_maj = report_bytes[2]
            v_min = report_bytes[3]
            v_pch = report_bytes[4]
            if v_maj > 0 or v_min > 0 or v_pch > 0:
                info.firmware_version = f"v{v_maj}.{v_min}.{v_pch}"
            else:
                info.firmware_version = None
            
        if len(report_bytes) >= 12:
            sn_bytes = report_bytes[5:12]
            sn_str = "".join([f"{b:02X}" for b in sn_bytes if b != 0])
            if sn_str:
                info.serial_number = sn_str
    return info


def parse_session_index_table(report_bytes: bytes) -> List[SessionInfo]:
    """Parses a 0x9C / 0xA5 storage index report or 0xEC segment metadata report into SessionInfo objects."""
    sessions = []
    if len(report_bytes) < 4:
        return sessions

    # Case 1: 0xEC Segment Metadata Report
    if report_bytes[0] == 0xEC:
        user_id = report_bytes[2] if len(report_bytes) > 2 else 1
        sess_id = report_bytes[3] if len(report_bytes) > 3 else 1
        
        # Bytes 10..13: 28-Bit Packed Little-Endian Integer (7-Bit Chunks): raw 2 Hz sample count.
        # The device takes two half-second readings per second and the records average them in
        # pairs, so seconds = ceil(count / 2) (PROTOCOL.md 3.2; an odd count keeps its last reading).
        b0 = report_bytes[10] if len(report_bytes) > 10 else 0
        b1 = report_bytes[11] if len(report_bytes) > 11 else 0
        b2 = report_bytes[12] if len(report_bytes) > 12 else 0
        b3 = report_bytes[13] if len(report_bytes) > 13 else 0
        raw_samples = (b0 & 0x7F) | ((b1 & 0x7F) << 7) | ((b2 & 0x7F) << 14) | ((b3 & 0x7F) << 21)
        duration_sec = (raw_samples + 1) // 2
        rec_cnt = duration_sec

        if sess_id == 0 and raw_samples == 0:
            return sessions

        dt = None
        if len(report_bytes) >= 10 and report_bytes[4] > 0:
            yr = 2000 + report_bytes[4] if report_bytes[4] < 100 else 2026
            mo = max(1, min(12, report_bytes[5]))
            dy = max(1, min(31, report_bytes[6]))
            hr = min(23, report_bytes[7])
            mi = min(59, report_bytes[8])
            sc = min(59, report_bytes[9])
            try:
                dt = datetime(yr, mo, dy, hr, mi, sc)
            except Exception:
                dt = None

        sessions.append(SessionInfo(
            session_id=sess_id if sess_id > 0 else 1,
            user_id=user_id if user_id > 0 else 1,
            record_count=rec_cnt,
            duration_sec=duration_sec,
            timestamp=dt,
            raw_samples=raw_samples,
        ))
        return sessions

    # Case 2: 0xF0 / 0x7D Multi-Session Index Table
    if report_bytes[0] in [0xF0, 0x7D]:
        total_sessions = report_bytes[2]
        if total_sessions == 0:
            return sessions

        offset = 3
        session_idx = 1
        stride = 8 if (len(report_bytes) - 3) >= (total_sessions * 8) else 6
        while offset + 4 <= len(report_bytes) and session_idx <= max(1, total_sessions):
            user_id = report_bytes[offset]
            sess_id = report_bytes[offset + 1] if report_bytes[offset + 1] > 0 else session_idx
            rec_cnt = (report_bytes[offset + 2] << 8) | report_bytes[offset + 3]

            dt = None
            if offset + 8 <= len(report_bytes) and stride >= 8:
                yr = 2000 + report_bytes[offset + 4] if report_bytes[offset + 4] < 100 else 2026
                mo = max(1, min(12, report_bytes[offset + 5]))
                dy = max(1, min(31, report_bytes[offset + 6]))
                hr = min(23, report_bytes[offset + 7])
                try:
                    dt = datetime(yr, mo, dy, hr, 0, 0)
                except Exception:
                    dt = None

            if (user_id != 0 or sess_id != 0 or rec_cnt != 0) and rec_cnt > 0:
                sessions.append(SessionInfo(
                    session_id=sess_id,
                    user_id=user_id if user_id > 0 else 1,
                    record_count=rec_cnt,
                    timestamp=dt
                ))
            offset += stride
            session_idx += 1

    return sessions


def parse_user_id_descriptor(report_bytes: bytes) -> int:
    """Parses User ID from 0xA2 session negotiation or 0xA5 index report payload."""
    if len(report_bytes) >= 3 and report_bytes[0] in [0xF0, 0x7D]:
        user_id = report_bytes[2]
        return user_id if 0 <= user_id <= 16 else 1
    return 1


def parse_ed_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
    """Parses 0xED / 0xEB session streaming and storage sub-chunks extracted from Pulsox PO-400 / CMS-60D v2."""
    datapoints = []
    if base_timestamp is None:
        base_timestamp = datetime.now()

    if len(report_bytes) < 6:
        return datapoints

    # 1. Check for 30-byte 0xED 0x04 Subframe
    if len(report_bytes) >= 30 and report_bytes[0] == 0xED and report_bytes[1] == 0x04:
        chk = sum(report_bytes[:29]) & 0x7F
        if chk == report_bytes[29] or report_bytes[29] == 0:
            dtype = report_bytes[2]
            flags = report_bytes[7]
            is_spo2 = (dtype == 0x01)
            samples = decode_ed_subframes([report_bytes[:30]], is_spo2=is_spo2)
            for s in samples:
                datapoints.append(DataPoint(
                    timestamp=base_timestamp,
                    spo2=s if is_spo2 else None,
                    heart_rate=s if not is_spo2 else None,
                    ppg_wave=0,
                    status_flags=flags,
                ))
            return datapoints

    # 2. Legacy / 6-byte sub-chunk parsing fallback
    idx = 0
    while idx + 6 <= len(report_bytes):
        header = report_bytes[idx]
        if header in [0xED, 0xEB]:
            ppg_wave = report_bytes[idx + 2]
            hr = report_bytes[idx + 3]
            flags = report_bytes[idx + 4]
            spo2 = report_bytes[idx + 5]

            if 30 <= spo2 <= 100 and 25 <= hr <= 250:
                datapoints.append(DataPoint(
                    timestamp=base_timestamp,
                    spo2=spo2,
                    heart_rate=hr,
                    ppg_wave=ppg_wave,
                    status_flags=flags
                ))
            idx += 6
        else:
            idx += 1

    return datapoints


parse_eb_data_frames = parse_ed_data_frames


def parse_stored_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
    """Parses 3-byte stored data records [second_tick, spo2, pulse_rate] from CMS60D v2 payload."""
    datapoints = []
    if base_timestamp is None:
        base_timestamp = datetime.now()

    idx = 0
    while idx + 3 <= len(report_bytes):
        b0 = report_bytes[idx]
        if (b0 & 0x80) != 0:
            b1 = report_bytes[idx + 1]
            b2 = report_bytes[idx + 2]
            if (b1 & 0x80) == 0 and (b2 & 0x80) == 0:
                spo2_raw = b1 & 0x7F
                pr_raw = b2 & 0x7F
                is_finger_off = (b0 & 0x20) != 0
                is_oob = spo2_raw == 0x7F or pr_raw == 0x7F or spo2_raw == 0 or pr_raw == 0
                if not (is_finger_off or is_oob):
                    datapoints.append(DataPoint(
                        timestamp=base_timestamp,
                        spo2=spo2_raw,
                        heart_rate=pr_raw,
                        ppg_wave=0,
                        status_flags=b0
                    ))
                idx += 3
            else:
                idx += 1
        else:
            idx += 1
    return datapoints


def parse_stored_download_block(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
    """Parses a 64-byte HID input report for all embedded 0xED 0x04 stored session sub-chunks."""
    datapoints = []
    if len(report_bytes) < 10:
        return datapoints
    if base_timestamp is None:
        base_timestamp = datetime.now()

    idx = 0
    while idx + 10 <= len(report_bytes):
        if report_bytes[idx] == 0xED and report_bytes[idx + 1] == 0x04:
            flags = report_bytes[idx + 7]
            spo2_raw = report_bytes[idx + 5]
            hr_raw = report_bytes[idx + 9]

            spo2_val = (spo2_raw - 18) if (48 <= spo2_raw <= 118) else None
            hr_val = (hr_raw - 56) if (81 <= hr_raw <= 306) else None

            spo2_valid = spo2_val is not None and 30 <= spo2_val <= 100
            hr_valid = hr_val is not None and 25 <= hr_val <= 250

            if spo2_valid and hr_valid:
                datapoints.append(DataPoint(
                    timestamp=base_timestamp,
                    spo2=spo2_val,
                    heart_rate=hr_val,
                    ppg_wave=0,
                    status_flags=flags
                ))
            step = 30 if (idx + 30 <= len(report_bytes)) else 10
            idx += step
        else:
            idx += 1
    return datapoints


def parse_hid_chunks(report_bytes: bytes, now: Optional[datetime] = None) -> Tuple[List[DataPoint], Optional[int], Optional[int], Optional[int]]:
    """Parses a raw HID report (18 to 64 bytes) into 6-byte chunks."""
    if now is None:
        now = datetime.now()

    datapoints: List[DataPoint] = []
    latest_spo2: Optional[int] = None
    latest_hr: Optional[int] = None
    latest_ppg: Optional[int] = None

    if len(report_bytes) < 6:
        return datapoints, latest_spo2, latest_hr, latest_ppg

    chunk_count = len(report_bytes) // 6
    for i in range(chunk_count):
        chunk = report_bytes[i * 6 : (i + 1) * 6]
        check_bit = chunk[0]
        update_bit = chunk[1]
        status_bit = chunk[2]
        val1 = chunk[3]
        val2 = chunk[4]

        if check_bit == 0 and update_bit == 0 and status_bit == 0 and val1 == 0 and val2 == 0:
            continue

        if update_bit == 0:
            latest_ppg = val1
        elif update_bit == 1:
            latest_hr = val1
            latest_spo2 = val2

        dp = DataPoint(
            timestamp=now,
            spo2=latest_spo2,
            heart_rate=latest_hr,
            ppg_wave=latest_ppg,
            status_flags=status_bit
        )
        datapoints.append(dp)

    return datapoints, latest_spo2, latest_hr, latest_ppg


class Parsers:
    """Stateless Factory for parsing inbound 64-byte USB HID Response Reports."""
    
    @staticmethod
    def parse_device_info(report_bytes: bytes) -> DeviceInfo:
        return parse_device_info(report_bytes)

    @staticmethod
    def parse_serial(report_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        return parse_serial_response(report_bytes)

    @staticmethod
    def parse_geometry(report_bytes: bytes) -> Optional[str]:
        return parse_storage_architecture_response(report_bytes)

    @staticmethod
    def parse_eb_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
        return parse_eb_data_frames(report_bytes, base_timestamp)

    @staticmethod
    def parse_ed_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
        return parse_ed_data_frames(report_bytes, base_timestamp)

    @staticmethod
    def decode_ed_subframes(subframes: List[bytes], is_spo2: bool = True) -> List[Optional[int]]:
        return decode_ed_subframes(subframes, is_spo2)

    @staticmethod
    def parse_session_index(report_bytes: bytes) -> List[SessionInfo]:
        return parse_session_index_table(report_bytes)

    @staticmethod
    def parse_user_id(report_bytes: bytes) -> int:
        return parse_user_id_descriptor(report_bytes)

    @staticmethod
    def parse_hid_chunks(report_bytes: bytes, now: Optional[datetime] = None) -> Tuple[List[DataPoint], Optional[int], Optional[int], Optional[int]]:
        return parse_hid_chunks(report_bytes, now)

    @staticmethod
    def parse_stored_block(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
        return parse_stored_download_block(report_bytes, base_timestamp)

    @staticmethod
    def parse_stored_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
        return parse_stored_data_frames(report_bytes, base_timestamp)
