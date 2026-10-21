"""Outbound 64-byte USB HID report builders and Commands factory."""

from datetime import datetime
from enum import IntEnum
from typing import List, Optional

from .models import Framing, Opcode
from .checksums import calc_checksum_7bit


class StorageSubcommand(IntEnum):
    """Storage Transfer Sub-commands for 0x9D Reports."""
    INIT = 0x02
    READ_BLOCK = 0x04
    FINALIZE = 0x7F


# Legacy Storage Subcommand Aliases
SUBCOMMAND_STORAGE_INIT = StorageSubcommand.INIT
SUBCOMMAND_STORAGE_READ_BLOCK = StorageSubcommand.READ_BLOCK
SUBCOMMAND_STORAGE_FINALIZE = StorageSubcommand.FINALIZE


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


def build_session_data_command(sub_cmd: int, block_id: int, sess_id: int) -> bytes:
    """Builds a 64-byte 0x9D HID storage command report matching exact PCAP / usbmon 9-byte framing.

    Header Framing (9 Bytes):
        [0x9D, sub_cmd, block_id, user_id, sess_id, 0x00, 0x00, 0x00, checksum]
    """
    if sub_cmd == SUBCOMMAND_STORAGE_INIT:
        b = [0x9D, 0x02, 0x7F, 0x7F, 0x7F, 0x00, 0x00, 0x00, 0x1C]
    elif sub_cmd == SUBCOMMAND_STORAGE_FINALIZE:
        b = [0x9D, 0x7F, 0x7F, 0x7F, 0x7F, 0x00, 0x00, 0x00, 0x19]
    else:
        base = [0x9D, sub_cmd & 0xFF, block_id & 0xFF, 0x01, sess_id & 0xFF, 0x00, 0x00, 0x00]
        chk = (sum(base[1:7]) + 0x1D) & 0xFF
        b = base + [chk]
    
    b.extend([0x00] * (64 - len(b)))
    return bytes(b)


def build_session_page_command(data_type: int, session_id: int, page_idx: int = 0, user_id: int = 1) -> bytes:
    """Builds a 64-byte 0x9D HID storage command report requesting flash subframes.

    Header Framing (9 Bytes):
        [0x9D, 0x04, data_type, user_id, session_id, sub_low, sub_high, 0x00, checksum]

    Checksum Formula:
        sum(header[0:8]) % 128
    """
    sub_low = page_idx & 0x7F
    sub_high = (page_idx >> 7) & 0x7F
    base = [0x9D, 0x04, data_type & 0xFF, user_id & 0xFF, session_id & 0xFF, sub_low, sub_high, 0x00]
    chk = calc_checksum_7bit(base)
    b = base + [chk]
    b.extend([0x00] * (64 - len(b)))
    return bytes(b)


def build_session_index_query_command() -> bytes:
    """Builds the 64-byte 0x9C report to query the stored session metadata index table."""
    return build_hid_command(Opcode.SESSION_INDEX_QUERY, [0x01, 0x1D])


def build_reset_session_index_command() -> bytes:
    """Builds the 64-byte 0x9C report to reset the flash session index iterator back to slot 0."""
    return build_hid_command(Opcode.SESSION_INDEX_QUERY, [0x80, 0x00])


def build_data_stream_query_command() -> bytes:
    """Builds the 64-byte 0x9B report to activate periodic data streaming."""
    return build_hid_command(Opcode.DATA_STREAM_QUERY, [0x00, 0x1B])


def build_stop_data_stream_command() -> bytes:
    """Builds the 64-byte 0x9B report to deactivate periodic data streaming (0x9B [0x80, 0x00])."""
    return build_hid_command(Opcode.DATA_STREAM_QUERY, [0x80, 0x00])


def build_storage_init_command() -> bytes:
    """Builds the 64-byte 0x9D storage transfer initialization report."""
    return build_session_data_command(SUBCOMMAND_STORAGE_INIT, 0x7F, 0x7F)


def build_read_spo2_block_command(session_id: int = 1) -> bytes:
    """Builds the 64-byte 0x9D 0x04 0x01 report to request the SpO2 data block (Block 1)."""
    return build_session_data_command(SUBCOMMAND_STORAGE_READ_BLOCK, 0x01, session_id)


def build_read_pulse_block_command(session_id: int = 1) -> bytes:
    """Builds the 64-byte 0x9D 0x04 0x02 report to request the Pulse Rate data block (Block 2)."""
    return build_session_data_command(SUBCOMMAND_STORAGE_READ_BLOCK, 0x02, session_id)


def build_segment_ack_command() -> bytes:
    """Builds the 64-byte 0x9D 0x02 non-destructive segment acknowledgment report."""
    return build_session_data_command(SUBCOMMAND_STORAGE_INIT, 0x7F, 0x7F)


def build_storage_block_command(block_id: int, session_id: int) -> bytes:
    """Builds the 64-byte 0x9D report to request a specific session block."""
    return build_session_data_command(SUBCOMMAND_STORAGE_READ_BLOCK, block_id, session_id)


def build_storage_finalize_command() -> bytes:
    """Builds the 64-byte 0x9D report with mode 0x7F (9D 7F 7F 7F 7F ...).

    DESTRUCTIVE: this is SpO2 Assistant's "Delete All" / auto-delete-after-saving, which erases
    every recording on the device (PROTOCOL.md 3.13, T-037). Nothing in fiedle400 sends it.
    """
    return build_session_data_command(SUBCOMMAND_STORAGE_FINALIZE, 0x7F, 0x7F)


def build_select_session_command(session_id: int) -> bytes:
    """Builds the 64-byte 0xA5 HID report to select an active session index slot."""
    return build_hid_command(0xA5, [session_id & 0xFF, 0x00])


def build_download_session_command(session_id: int) -> bytes:
    """Builds the 64-byte 0xA6 HID report to initiate session download handshake."""
    return build_hid_command(0xA6, [session_id & 0xFF, 0x00])


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


class Commands:
    """Stateless Factory for constructing 64-byte USB HID Outbound Command Reports."""
    
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
    def reset_session_index() -> bytes:
        return build_reset_session_index_command()

    @staticmethod
    def query_data_stream() -> bytes:
        return build_data_stream_query_command()

    @staticmethod
    def stop_data_stream() -> bytes:
        return build_stop_data_stream_command()

    @staticmethod
    def storage_init() -> bytes:
        return build_storage_init_command()

    @staticmethod
    def storage_block(block_id: int, session_id: int) -> bytes:
        return build_storage_block_command(block_id, session_id)

    @staticmethod
    def session_page(data_type: int, session_id: int, page_idx: int = 0, user_id: int = 1) -> bytes:
        return build_session_page_command(data_type, session_id, page_idx, user_id)

    @staticmethod
    def segment_ack() -> bytes:
        return build_segment_ack_command()

    @staticmethod
    def read_spo2_block(session_id: int = 1) -> bytes:
        return build_read_spo2_block_command(session_id)

    @staticmethod
    def read_pulse_block(session_id: int = 1) -> bytes:
        return build_read_pulse_block_command(session_id)

    @staticmethod
    def storage_finalize() -> bytes:
        return build_storage_finalize_command()

    @staticmethod
    def read_time() -> bytes:
        return build_read_time_command()

    @staticmethod
    def set_time(dt: Optional[datetime] = None) -> bytes:
        return build_set_time_command(dt)

    @staticmethod
    def select_session(session_id: int) -> bytes:
        return build_select_session_command(session_id)

    @staticmethod
    def download_session(session_id: int) -> bytes:
        return build_download_session_command(session_id)
