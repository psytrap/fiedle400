"""Protocol data models, opcodes, and framing constants for Pulsox PO-400."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional


class Framing(IntEnum):
    """Protocol HID Report Framing and Header Constants."""
    REPORT_LENGTH = 64
    HEADER_BYTE_0 = 0x7D
    HEADER_BYTE_1 = 0x81
    PADDING_BYTE = 0x80
    SESSION_INDEX_HEADER = 0xEC  # Response report header byte for stored session index metadata
    MAX_SESSION_SLOTS = 32       # Maximum stored session slot capacity in device EEPROM/Flash


# --- Protocol Timing Constants ---
# Microcontrollers over USB HID require small delays between writes to flush output buffers
# and allow report state machines to transition without packet drops.
HID_POLL_INTERVAL_SEC = 0.002   # 2ms poll interval to avoid high CPU utilization during HID reads
HID_READ_TIMEOUT_SEC = 0.25     # 250ms maximum timeout when waiting for a specific HID response packet
COMMAND_ACK_DELAY_SEC = 0.05    # 50ms settling time after issuing command reports before reading ACKs


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


@dataclass
class DataPoint:
    """Instantaneous physiological sample."""
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
    """Stored recording session metadata."""
    session_id: int
    user_id: int = 1
    record_count: int = 0
    duration_sec: int = 0
    timestamp: Optional[datetime] = None
    raw_samples: int = 0   # raw 2 Hz readings stored (0xEC header); record_count and duration_sec are 1 Hz

    @property
    def duration_seconds(self) -> int:
        """Returns duration in seconds."""
        if self.duration_sec > 0:
            return self.duration_sec
        return max(0, self.record_count)

    @property
    def duration_str(self) -> str:
        """Formats record count into human-readable duration (e.g., '3h 37m 36s', '42m 44s', '15s')."""
        total_sec = self.duration_seconds
        if total_sec <= 0:
            return "0s"
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hrs > 0:
            return f"{hrs}h {mins:02d}m {secs:02d}s"
        elif mins > 0:
            return f"{mins}m {secs:02d}s"
        else:
            return f"{secs}s"


@dataclass
class DeviceInfo:
    """Hardware and firmware descriptors."""
    firmware_version: Optional[str] = None
    hardware_id: Optional[str] = None
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    serial_number: Optional[str] = None
    user_profile: Optional[str] = None
    flash_geometry: Optional[str] = None


@dataclass
class DecodedPacket:
    """Represents a single parsed packet event detected from the byte stream."""
    packet_type: str  # "SESSION_INDEX", "STORED_BLOCK", "LIVE_STREAM", "COMMAND_ACK", "RTC_RESPONSE", "DEVICE_INFO", "FLASH_SENTINEL"
    timestamp: datetime
    spo2: Optional[int] = None
    heart_rate: Optional[int] = None
    ppg_wave: int = 0
    status_flags: int = 0x00
    status_str: str = "ok"
    session_info: Optional[SessionInfo] = None
    device_info: Optional[DeviceInfo] = None
    raw_payload: Optional[bytes] = None
    block_id: Optional[int] = None
    seq: Optional[int] = None
    sequence_gap: bool = False
    expected_seq: Optional[int] = None
    invalid_sample: bool = False  # stored series pair outside the physiological range (finger out): value is None
