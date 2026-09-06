"""Pulsox PO-400 Protocol Package.

Exports all wire framing, data models, checksums, commands, parsers, and decompression utilities.
"""

from .models import (
    Framing,
    Opcode,
    DataPoint,
    SessionInfo,
    DeviceInfo,
    DecodedPacket,
    HID_POLL_INTERVAL_SEC,
    HID_READ_TIMEOUT_SEC,
    COMMAND_ACK_DELAY_SEC,
)

from .checksums import (
    calc_checksum_7bit,
    pack_7bit_le_14bit,
    unpack_7bit_le_14bit,
    pack_7bit_le_28bit,
    unpack_7bit_le_28bit,
)

from .decompression import (
    unmask_subframe_msb,
    decode_status_flags,
    decode_ed_subframes,
)

from .commands import (
    Commands,
    StorageSubcommand,
    SUBCOMMAND_STORAGE_INIT,
    SUBCOMMAND_STORAGE_READ_BLOCK,
    SUBCOMMAND_STORAGE_FINALIZE,
    build_hid_command,
    build_unlock_negotiate_handshake,
    build_session_data_command,
    build_session_page_command,
    build_session_index_query_command,
    build_reset_session_index_command,
    build_data_stream_query_command,
    build_stop_data_stream_command,
    build_storage_init_command,
    build_read_spo2_block_command,
    build_read_pulse_block_command,
    build_segment_ack_command,
    build_storage_block_command,
    build_storage_finalize_command,
    build_select_session_command,
    build_download_session_command,
    build_set_time_command,
    build_read_time_command,
)

from .parsers import (
    Parsers,
    parse_rtc_response,
    parse_segment_metadata,
    parse_serial_response,
    parse_storage_architecture_response,
    parse_device_info,
    parse_session_index_table,
    parse_user_id_descriptor,
    parse_ed_data_frames,
    parse_eb_data_frames,
    parse_stored_data_frames,
    parse_stored_download_block,
    parse_hid_chunks,
)

from .hardware import (
    decode_usb_vid_pid,
    KNOWN_DEVICES,
    HARDWARE_PROFILES,
)

__all__ = [
    # Models
    "Framing",
    "Opcode",
    "DataPoint",
    "SessionInfo",
    "DeviceInfo",
    "DecodedPacket",
    "HID_POLL_INTERVAL_SEC",
    "HID_READ_TIMEOUT_SEC",
    "COMMAND_ACK_DELAY_SEC",
    # Checksums
    "calc_checksum_7bit",
    "pack_7bit_le_14bit",
    "unpack_7bit_le_14bit",
    "pack_7bit_le_28bit",
    "unpack_7bit_le_28bit",
    # Decompression
    "unmask_subframe_msb",
    "decode_status_flags",
    "decode_ed_subframes",
    # Commands
    "Commands",
    "StorageSubcommand",
    "SUBCOMMAND_STORAGE_INIT",
    "SUBCOMMAND_STORAGE_READ_BLOCK",
    "SUBCOMMAND_STORAGE_FINALIZE",
    "build_hid_command",
    "build_unlock_negotiate_handshake",
    "build_session_data_command",
    "build_session_page_command",
    "build_session_index_query_command",
    "build_reset_session_index_command",
    "build_data_stream_query_command",
    "build_stop_data_stream_command",
    "build_storage_init_command",
    "build_read_spo2_block_command",
    "build_read_pulse_block_command",
    "build_segment_ack_command",
    "build_storage_block_command",
    "build_storage_finalize_command",
    "build_select_session_command",
    "build_download_session_command",
    "build_set_time_command",
    "build_read_time_command",
    # Parsers
    "Parsers",
    "parse_rtc_response",
    "parse_segment_metadata",
    "parse_serial_response",
    "parse_storage_architecture_response",
    "parse_device_info",
    "parse_session_index_table",
    "parse_user_id_descriptor",
    "parse_ed_data_frames",
    "parse_eb_data_frames",
    "parse_stored_data_frames",
    "parse_stored_download_block",
    "parse_hid_chunks",
    # Hardware
    "decode_usb_vid_pid",
    "KNOWN_DEVICES",
    "HARDWARE_PROFILES",
]
