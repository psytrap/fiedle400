"""Export module for Pulsox PO-400 session data.

Supports exporting session records to:
- Contec .SpO2 binary format (default, compatible with SpO2 Assistant and OSCAR)
- CSV (Comma-Separated Values)
- JSON (JavaScript Object Notation)
"""

import csv
import json
import os
import struct
from datetime import datetime
from typing import Any, Dict, List, Optional

# Header length for .SpO2 binary format (0x043C)
SPO2_HEADER_SIZE = 1084

# Magic constants
SPO2_MAGIC = 0x0358  # 856
SPO2_VERSION = 1
SPO2_CHANNEL_FLAG = 1
SPO2_TAG_BLE = b"B\x00L\x00E\x00"

# Sentinel bytes for probe-out / disconnected / invalid data
SPO2_INVALID_SPO2 = 127  # 0x7F
SPO2_INVALID_HR = 255    # 0xFF


def parse_record_datetime(ts_val: Any) -> Optional[datetime]:
    """Helper to parse a timestamp from ISO string or datetime object."""
    if isinstance(ts_val, datetime):
        return ts_val
    if isinstance(ts_val, str):
        try:
            return datetime.fromisoformat(ts_val)
        except ValueError:
            pass
    return None


def build_spo2_binary(
    records: List[Dict[str, Any]],
    start_dt: Optional[datetime] = None,
) -> bytes:
    """Build binary .SpO2 file content from extracted session records.

    Args:
        records: List of session record dictionaries containing 'spo2', 'heart_rate', and 'timestamp'.
        start_dt: Explicit recording start datetime. If None, derived from records[0] or datetime.now().

    Returns:
        bytes: Complete binary .SpO2 file payload (1084-byte header + N * 2 bytes).
    """
    if start_dt is None:
        if records and records[0].get("timestamp"):
            start_dt = parse_record_datetime(records[0]["timestamp"])
        if start_dt is None:
            start_dt = datetime.now()

    sample_count = len(records)
    hdr = bytearray(SPO2_HEADER_SIZE)

    # 0x0000: Magic (0x0358 = 856), 0x0004: Version (1)
    struct.pack_into("<II", hdr, 0x0000, SPO2_MAGIC, SPO2_VERSION)

    # 0x0358: Channel flag (1)
    struct.pack_into("<I", hdr, 0x0358, SPO2_CHANNEL_FLAG)

    # 0x0360: Protocol tag "BLE\0" (UTF-16LE)
    hdr[0x0360:0x0366] = SPO2_TAG_BLE

    # 0x0420: Datetime block and total 1 Hz sample count
    struct.pack_into(
        "<7I",
        hdr,
        0x0420,
        start_dt.year,
        start_dt.month,
        start_dt.day,
        start_dt.hour,
        start_dt.minute,
        start_dt.second,
        sample_count,
    )

    # Payload: 2 bytes per second [SpO2 (uint8), Heart Rate (uint8)]
    payload = bytearray(sample_count * 2)
    for i, r in enumerate(records):
        spo2 = r.get("spo2")
        hr = r.get("heart_rate")

        # Check for valid physiological ranges
        s_byte = int(spo2) if (spo2 is not None and 1 <= int(spo2) <= 100) else SPO2_INVALID_SPO2
        h_byte = int(hr) if (hr is not None and 1 <= int(hr) <= 250) else SPO2_INVALID_HR

        payload[i * 2] = s_byte
        payload[i * 2 + 1] = h_byte

    return bytes(hdr + payload)


def export_records(
    records: List[Dict[str, Any]],
    output_filename: Optional[str] = None,
    fmt: str = "spo2",
    output_dir: Optional[str] = None,
) -> str:
    """Save extracted records into the requested file format (.spo2, .csv, or .json).

    Args:
        records: List of record dictionaries.
        output_filename: Target path or filename. If omitted, a timestamped name is generated.
        fmt: Target format ('spo2', 'csv', or 'json'). Ignored if output_filename has a recognized extension.
        output_dir: Directory for the generated name. Ignored when output_filename is given;
            omitted means the current directory, preserving the plain-CLI behaviour.

    Returns:
        str: Absolute path of the saved output file.
    """
    clean_fmt = fmt.lower().lstrip(".")

    # Auto-detect format from output_filename extension if supplied
    if output_filename:
        _, ext = os.path.splitext(output_filename)
        ext_clean = ext.lower().lstrip(".")
        if ext_clean in ("spo2", "csv", "json"):
            clean_fmt = ext_clean

    if not output_filename:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"fiedle400_all_sessions_{timestamp_str}.{clean_fmt}"
        if output_dir:
            output_filename = os.path.join(output_dir, output_filename)

    output_path = os.path.abspath(output_filename)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if clean_fmt == "spo2":
        data = build_spo2_binary(records)
        with open(output_path, "wb") as f:
            f.write(data)
    elif clean_fmt == "csv":
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["session_id", "user_id", "block_id", "seq", "timestamp", "spo2", "heart_rate", "flags"],
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(records)
    elif clean_fmt == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    else:
        raise ValueError(f"Unsupported export format '{clean_fmt}'. Supported: 'spo2', 'csv', 'json'.")

    return output_path
