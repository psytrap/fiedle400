"""Pulsox PO-400 USB HID Protocol Decoder and Encoder.

Handles framing and parsing of 64-byte / 18-byte HID reports into structured
SpO2 %, Heart Rate (BPM), and Plethysmogram (PPG) waveform objects.

TODO: In a future refactoring pass, split this module into dedicated sub-modules:
  - po400/models.py   (Dataclasses: DataPoint, SessionInfo, DeviceInfo, Opcode)
  - po400/commands.py (Outbound packet Builders / Commands class)
  - po400/parsers.py  (Inbound packet Decoders / Parsers class)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Tuple, Any


class Framing(IntEnum):
    """Protocol HID Report Framing and Header Constants."""
    REPORT_LENGTH = 64
    HEADER_BYTE_0 = 0x7D
    HEADER_BYTE_1 = 0x81
    PADDING_BYTE = 0x80





class Opcode(IntEnum):
    """Protocol Command Opcodes for Pulsox PO-400 / Contec CMS-60D v2."""
    UNLOCK_HANDSHAKE = 0xA7
    STORAGE_NEGOTIATION = 0xA2
    READ_RTC = 0x82
    SET_RTC = 0x83
    DEVICE_INFO = 0x8E
    SESSION_INDEX_QUERY = 0x9C
    DATA_STREAM_QUERY = 0x9B
    STORAGE_READ = 0x9D
    FLASH_CLEAR = 0xAA
    GEOMETRY_QUERY = 0x9E


# --- Protocol Data Classes ---
@dataclass
class DataPoint:
    timestamp: datetime
    spo2: Optional[int] = None
    heart_rate: Optional[int] = None
    ppg_wave: Optional[int] = None
    status_flags: int = 0

    @property
    def is_valid(self) -> bool:
        """Returns True if SpO2 and Heart Rate readings are within valid physiological range."""
        if self.spo2 is not None and self.heart_rate is not None:
            return 30 <= self.spo2 <= 100 and 25 <= self.heart_rate <= 250
        return False


@dataclass
class SessionInfo:
    session_id: int
    user_id: int = 1
    record_count: int = 0
    timestamp: Optional[datetime] = None


@dataclass
class DeviceInfo:
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    user_profile: Optional[str] = None
    flash_geometry: Optional[str] = None



class Commands:
    """Stateless Factory for constructing 64-byte USB HID Outbound Command Reports under Option A."""
    
    @staticmethod
    def build_hid(cmd_code: int, args: Optional[List[int]] = None) -> bytes:
        return build_hid_command(cmd_code, args)

    @staticmethod
    def unlock_handshake() -> bytes:
        return build_unlock_negotiate_handshake()

    @staticmethod
    def session_data(sub_cmd: int, block_id: int, sess_id: int) -> bytes:
        return build_session_data_command(sub_cmd, block_id, sess_id)

    @staticmethod
    def query_sessions() -> bytes:
        return build_session_index_query_command()

    @staticmethod
    def query_data_stream() -> bytes:
        return build_data_stream_query_command()

    @staticmethod
    def storage_init() -> bytes:
        return build_storage_init_command()

    @staticmethod
    def storage_block(block_id: int, session_id: int) -> bytes:
        return build_storage_block_command(block_id, session_id)

    @staticmethod
    def storage_finalize() -> bytes:
        return build_storage_finalize_command()

    @staticmethod
    def set_time(dt: Optional[datetime] = None) -> bytes:
        return build_set_time_command(dt)

    @staticmethod
    def read_time() -> bytes:
        return build_read_time_command()


class Parsers:
    """Stateless Decoders for parsing USB HID Inbound Input Reports under Option A."""

    @staticmethod
    def parse_rtc_time(report_bytes: bytes) -> Optional[datetime]:
        return parse_rtc_response(report_bytes)

    @staticmethod
    def parse_segment_metadata(report_bytes: bytes) -> Optional[Tuple[datetime, str]]:
        return parse_segment_metadata(report_bytes)

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
    def parse_session_index(report_bytes: bytes) -> List[SessionInfo]:
        return parse_session_index_table(report_bytes)

    @staticmethod
    def parse_device_info(report_bytes: bytes) -> DeviceInfo:
        return parse_device_info(report_bytes)

    @staticmethod
    def parse_user_id(report_bytes: bytes) -> int:
        return parse_user_id_descriptor(report_bytes)

    @staticmethod
    def parse_hid_chunks(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> Tuple[List[DataPoint], Optional[int], Optional[int], Optional[int]]:
        return parse_hid_chunks(report_bytes, base_timestamp)

    @staticmethod
    def parse_stored_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
        return parse_stored_data_frames(report_bytes, base_timestamp)



def build_hid_command(cmd_code: int, args: Optional[List[int]] = None) -> bytes:
    """Builds a 64-byte HID output report formatted for Contec/GigaDevice HID controllers.
    
    Format: 0x7D, 0x81, cmd_code, [args...], padded to 64 bytes with 0x80.
    """
    payload = [Framing.HEADER_BYTE_0, Framing.HEADER_BYTE_1, cmd_code & 0xFF]
    if args:
        payload.extend([a & 0xFF for a in args])
    
    padding_len = Framing.REPORT_LENGTH - len(payload)
    return bytes(payload + [Framing.PADDING_BYTE] * padding_len)


def build_unlock_negotiate_handshake() -> bytes:
    """Builds the 64-byte combined unlock & storage negotiation HID report (Packet #549).
    
    Concatenates Opcode.UNLOCK_HANDSHAKE (0xA7) and Opcode.STORAGE_NEGOTIATION (0xA2)
    to unlock the PO-400 microcontroller state machine.
    """
    sub_unlock = [Framing.HEADER_BYTE_0, Framing.HEADER_BYTE_1, Opcode.UNLOCK_HANDSHAKE] + [Framing.PADDING_BYTE] * 6
    sub_negotiate = [Framing.HEADER_BYTE_0, Framing.HEADER_BYTE_1, Opcode.STORAGE_NEGOTIATION]
    payload = sub_unlock + sub_negotiate
    padding_len = Framing.REPORT_LENGTH - len(payload)
    return bytes(payload + [Framing.PADDING_BYTE] * padding_len)


class StorageSubcommand(IntEnum):
    """Storage Transfer Sub-commands for 0x9D Reports."""
    INIT = 0x02
    READ_BLOCK = 0x04
    FINALIZE = 0x7F


# Legacy Storage Subcommand Aliases
SUBCOMMAND_STORAGE_INIT = StorageSubcommand.INIT
SUBCOMMAND_STORAGE_READ_BLOCK = StorageSubcommand.READ_BLOCK
SUBCOMMAND_STORAGE_FINALIZE = StorageSubcommand.FINALIZE


def build_session_data_command(sub_cmd: int, block_id: int, sess_id: int) -> bytes:
    """Builds a 64-byte 0x9D HID storage command report."""
    buf = [Opcode.STORAGE_READ, sub_cmd & 0xFF, block_id & 0xFF, 0x01, sess_id & 0xFF, 0x00, 0x00]
    checksum = sum(buf) & 0xFF
    buf.append(checksum)
    padding_len = Framing.REPORT_LENGTH - len(buf)
    return bytes(buf + [0x00] * padding_len)


def build_session_index_query_command() -> bytes:
    """Builds the 64-byte 0x9C report to query the stored session metadata index table."""
    return build_hid_command(Opcode.SESSION_INDEX_QUERY, [0x01, 0x1D])


def build_data_stream_query_command() -> bytes:
    """Builds the 64-byte 0x9B report to activate stored data streaming."""
    return build_hid_command(Opcode.DATA_STREAM_QUERY, [0x00, 0x1B])


def build_storage_init_command() -> bytes:
    """Builds the 64-byte 0x9D storage transfer initialization report."""
    return build_session_data_command(SUBCOMMAND_STORAGE_INIT, 0x7F, 0x7F)


def build_storage_block_command(block_id: int, session_id: int) -> bytes:
    """Builds the 64-byte 0x9D report to request a specific session block."""
    return build_session_data_command(SUBCOMMAND_STORAGE_READ_BLOCK, block_id, session_id)


def build_storage_finalize_command() -> bytes:
    """Builds the 64-byte 0x9D storage transfer finalization report."""
    return build_session_data_command(SUBCOMMAND_STORAGE_FINALIZE, 0x7F, 0x7F)


def build_set_time_command(dt: Optional[datetime] = None) -> bytes:
    """Builds a 64-byte 0x83 HID report to set the device Real-Time Clock (RTC)."""
    if dt is None:
        dt = datetime.now()
    yy = dt.year % 100
    mm = dt.month
    dd = dt.day
    hh = dt.hour
    mi = dt.minute
    ss = dt.second
    
    buf = [0x83, yy, mm, dd, hh, mi, ss]
    checksum = (0x133 - sum(buf)) & 0xFF
    payload = buf + [checksum, 0x01, 0x34]
    padding_len = 64 - len(payload)
    return bytes(payload + [0x00] * padding_len)


def build_read_time_command() -> bytes:
    """Builds a 64-byte 0x82 HID report to read the active device Real-Time Clock (RTC)."""
    buf = [0x82, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
    checksum = sum(buf) & 0xFF
    buf.append(checksum)
    padding_len = 64 - len(buf)
    return bytes(buf + [0x00] * padding_len)


def parse_rtc_response(report_bytes: bytes) -> Optional[datetime]:
    """Parses a 0xF2 RTC timestamp input report returned by PO-400 device."""
    if len(report_bytes) >= 8 and report_bytes[0] in [0xF2, 0xF0]:
        # Handle 0xF2 format: [0xF2, 0x00, 0x00, YY, MM, DD, hh, mm, ss, ...]
        offset = 3 if report_bytes[0] == 0xF2 else 2
        if offset + 6 <= len(report_bytes):
            yr = 2000 + report_bytes[offset]
            mo = max(1, min(12, report_bytes[offset + 1]))
            dy = max(1, min(31, report_bytes[offset + 2]))
            hr = min(23, report_bytes[offset + 3])
            mi = min(59, report_bytes[offset + 4])
            sc = min(59, report_bytes[offset + 5])
            try:
                return datetime(yr, mo, dy, hr, mi, sc)
            except Exception:
                return None
    return None


def parse_segment_metadata(report_bytes: bytes) -> Optional[Tuple[datetime, str]]:
    """Parses 0xEC segment index report for session start time and user name."""
    if len(report_bytes) >= 16 and report_bytes[0] == 0xEC:
        # Format: [0xEC, 0x00, 0x01, 0x01, YY, MM, DD, hh, mm, ss, ...]
        yr = 2000 + report_bytes[4] if report_bytes[4] < 100 else 2026
        mo = max(1, min(12, report_bytes[5]))
        dy = max(1, min(31, report_bytes[6]))
        hr = min(23, report_bytes[7])
        mi = min(59, report_bytes[8])
        sc = min(59, report_bytes[9])
        
        # User name string starting at byte 15
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
    """Parses 0x9E / 0x9F Flash storage architecture report into strictly dynamic payload and block size string."""
    if len(report_bytes) >= 4 and report_bytes[0] in [0x9E, 0x9F, 0xF0]:
        chunk_size = report_bytes[1]
        block_factor = report_bytes[2]
        if chunk_size > 0:
            if block_factor > 0:
                return f"{chunk_size} Bytes Sub-chunk Payload, {block_factor} KB Address Block"
            return f"{chunk_size} Bytes Sub-chunk Payload"
    return None


def parse_eb_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
    """Parses 0xEB / 0xED session streaming reports extracted from pcap/bum400.pcapng.
    
    Frame Structure (0xEB Sub-chunks):
        [0xEB, status, index, heart_rate, flags, spo2]
    """
    datapoints = []
    if base_timestamp is None:
        base_timestamp = datetime.now()

    if len(report_bytes) < 6:
        return datapoints

    idx = 0
    while idx + 6 <= len(report_bytes):
        header = report_bytes[idx]
        if header in [0xEB, 0xED]:
            sub_status = report_bytes[idx + 1]
            sub_idx = report_bytes[idx + 2]
            hr = report_bytes[idx + 3]
            flags = report_bytes[idx + 4]
            spo2 = report_bytes[idx + 5]

            # Validate range: SpO2 (30..100) and HR (30..250)
            if 30 <= spo2 <= 100 and 30 <= hr <= 250:
                datapoints.append(DataPoint(
                    timestamp=base_timestamp,
                    spo2=spo2,
                    heart_rate=hr,
                    ppg_wave=0,
                    status_flags=flags
                ))
            idx += 6
        else:
            idx += 1

    return datapoints


@dataclass
class SessionInfo:
    session_id: int
    user_id: int
    record_count: int
    timestamp: Optional[datetime] = None


@dataclass
class DeviceInfo:
    firmware_version: Optional[str] = None
    hardware_id: Optional[str] = None
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    serial_number: Optional[str] = None
    user_profile: Optional[str] = None
    flash_geometry: Optional[str] = None





def parse_stored_data_frames(report_bytes: bytes, base_timestamp: Optional[datetime] = None) -> List[DataPoint]:
    """Parses 3-byte stored data records [second_tick, spo2, pulse_rate] from CMS60D v2 payload.
    
    Data Framing Rules (v2 Protocol):
        Byte 0: Relative Time Offset / Second Tick
        Byte 1: SpO2 percentage (0-100)
        Byte 2: Pulse Rate BPM (0-254)
        
    Synchronization & Error Masking:
        - Bit 7 Sync Check: Sync byte has (byte & 0x80) != 0
        - Finger-Off / Out-of-Bounds: Masked if status & 0x20 != 0 or value == 0x7F (127)
    """
    datapoints = []
    if base_timestamp is None:
        base_timestamp = datetime.now()

    # Search for Bit-7 Sync Header Byte ((b & 0x80) != 0)
    idx = 0
    while idx + 3 <= len(report_bytes):
        b0 = report_bytes[idx]
        
        # Header byte b0 must have Bit 7 set
        if (b0 & 0x80) != 0:
            b1 = report_bytes[idx + 1]
            b2 = report_bytes[idx + 2]

            # Subsequent bytes b1 and b2 MUST satisfy (byte & 0x80) == 0
            if (b1 & 0x80) == 0 and (b2 & 0x80) == 0:
                tick = b0 & 0x7F
                spo2_raw = b1 & 0x7F
                pr_raw = b2 & 0x7F
                
                # Finger-off status check (b0 & 0x20 != 0) or out-of-bounds error marker (0x7F)
                is_finger_off = (b0 & 0x20) != 0
                is_oob = spo2_raw == 0x7F or pr_raw == 0x7F or spo2_raw == 0 or pr_raw == 0
                is_valid = not (is_finger_off or is_oob)

                if is_valid:
                    dp_time = base_timestamp
                    datapoints.append(DataPoint(
                        timestamp=dp_time,
                        spo2=spo2_raw,
                        heart_rate=pr_raw,
                        ppg_wave=0,
                        status_flags=b0
                    ))
                idx += 3
            else:
                # Subsequent byte failed (byte & 0x80) == 0 condition; seek next header
                idx += 1
        else:
            idx += 1

    return datapoints


def parse_user_id_descriptor(report_bytes: bytes) -> int:
    """Parses User ID from 0xA2 session negotiation or 0xA5 index report payload."""
    if len(report_bytes) >= 3 and report_bytes[0] in [0xF0, 0x7D]:
        user_id = report_bytes[2]
        return user_id if 0 <= user_id <= 16 else 1
    return 1


def decode_usb_vid_pid(vid_hex: str, pid_hex: str) -> Tuple[str, str]:
    """Decodes a USB Vendor & Product ID (VID:PID) into known pulse oximeter hardware architecture.
    
    Returns:
        tuple: (architecture_description, source_citation)
    """
    vid_clean = vid_hex.upper().replace("0X", "")[-4:].zfill(4)
    pid_clean = pid_hex.upper().replace("0X", "")[-4:].zfill(4)
    key = f"{vid_clean}:{pid_clean}"
    
    known_devices = {
        "28E9:028A": (
            "GigaDevice MCU HID Oximeter (CMS-60D v2 / Pulsox PO-400)",
            "SpO2_Assistant_v3_Setup.exe INF file hid_device.inf & USB-IF 0x28E9 Registry"
        ),
        "10C4:EA60": (
            "Silicon Labs CP210x USB-to-UART (CMS-50D+)",
            "SpO2_Assistant_v3_Setup.exe INF file SiUSBXp.inf & atbrask/CMS50Dplus project"
        ),
        "0403:6001": (
            "FTDI FT232 Serial Oximeter (Legacy CMS-50/60 Models)",
            "Subsurface-divelog project & Linux usb.ids database"
        ),
    }
    
    return known_devices.get(
        key,
        ("Unknown USB Device", "Unregistered in Contec/Pulsox driver database")
    )


def parse_device_info(report_bytes: bytes) -> DeviceInfo:
    """Parses device info reports (0xAD, 0x81, 0x8E) into structured DeviceInfo object."""
    info = DeviceInfo()
    if len(report_bytes) >= 5 and report_bytes[0] in [0xF0, 0x81, 0xFE, 0xF1]:
        # Handle 0x81 firmware version report: [0x81, maj, min, patch, ...]
        if report_bytes[0] == 0x81 and len(report_bytes) >= 4:
            v_maj = report_bytes[1]
            v_min = report_bytes[2]
            v_pch = report_bytes[3]
            if v_maj > 0 or v_min > 0 or v_pch > 0:
                info.firmware_version = f"v{v_maj}.{v_min}.{v_pch}"
        # Handle 0xF0 0xAD response report
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
    """Parses a 0xA5 storage index report into structured SessionInfo objects.
    
    Format:
        Byte 0: 0xF0 Header
        Byte 1: 0x70 ACK / Status
        Byte 2: Total Session Count (N)
        Byte 3..M: Session Records [user_id, session_id, count_hi, count_lo, ...]
    """
    sessions = []
    if len(report_bytes) < 4:
        return sessions

    # Check report header and total sessions count (Byte 2)
    if report_bytes[0] not in [0xF0, 0x7D]:
        return sessions

    total_sessions = report_bytes[2]
    if total_sessions == 0:
        return sessions

    # Parse 8-byte session entries
    offset = 3
    session_idx = 1
    while offset + 6 <= len(report_bytes) and session_idx <= max(1, total_sessions):
        user_id = report_bytes[offset]
        sess_id = report_bytes[offset + 1] if report_bytes[offset + 1] > 0 else session_idx
        rec_cnt = (report_bytes[offset + 2] << 8) | report_bytes[offset + 3]
        
        # Check if optional 6-byte date format is present: [year, month, day, hour, min, sec]
        dt = None
        if offset + 9 <= len(report_bytes):
            yr = 2000 + report_bytes[offset + 3] if report_bytes[offset + 3] < 100 else 2026
            mo = max(1, min(12, report_bytes[offset + 4]))
            dy = max(1, min(31, report_bytes[offset + 5]))
            hr = min(23, report_bytes[offset + 6])
            mi = min(59, report_bytes[offset + 7])
            sc = min(59, report_bytes[offset + 8])
            try:
                dt = datetime(yr, mo, dy, hr, mi, sc)
            except Exception:
                dt = None

        if user_id != 0 or sess_id != 0 or rec_cnt != 0:
            sessions.append(SessionInfo(
                session_id=sess_id,
                user_id=user_id,
                record_count=rec_cnt,
                timestamp=dt
            ))
        offset += 6
        session_idx += 1

    return sessions


def parse_hid_chunks(report_bytes: bytes, now: Optional[datetime] = None) -> Tuple[List[DataPoint], Optional[int], Optional[int], Optional[int]]:
    """Parses a raw HID report (18 to 64 bytes) into 6-byte chunks.
    
    Returns:
        tuple: (list_of_datapoints, latest_spo2, latest_hr, latest_ppg)
    """
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

        # Ignore empty/idle frames
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
