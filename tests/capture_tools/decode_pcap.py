#!/usr/bin/env python3
"""Contec / Pulsox PO-400 PCAP & PCAPNG Packet Capture Decoder

Decodes recorded USB HID download traffic (.pcap or .pcapng files) from PO-400 / CMS-60D
pulse oximeter stored recording download sessions into CSV or JSON output formats.

Supports:
    - PCAP (Legacy header) and PCAPNG (Section Header & Enhanced Packet Blocks)
    - Dynamic USB URB header length parsing (27-byte 0x1B, 28-byte 0x1C, 64-byte 0x40)
    - Session index metadata reports (0xEC)
    - Stored recording session download blocks (0xED 0x04)

Usage:
    python3 decode_pcap.py <file.pcap|file.pcapng> [-f csv|json] [-o output] [--no-invalid]
"""

import argparse
import csv
import json
import os
import struct
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

# Ensure the fiedle400 package (repository root, two levels up) can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fiedle400.protocol import Parsers
from fiedle400.serial_engine import SerialPacketDetector, SerialByteStreamBuffer


def parse_pcap_file(filepath: str) -> List[Tuple[int, bytes]]:
    """Parses a .pcap or .pcapng file and returns raw (endpoint_id, payload_bytes) tuples."""
    with open(filepath, "rb") as file:
        data = file.read()

    reports = []
    if len(data) < 24:
        return reports

    # 1. PCAPNG Format (Section Header Block Magic: 0x0A0D0D0A)
    if data.startswith(b"\x0a\x0d\x0d\x0a"):
        position = 0
        while position < len(data):
            if position + 8 > len(data):
                break
            block_type, block_length = struct.unpack("<II", data[position : position + 8])
            if block_length < 12 or position + block_length > len(data):
                break
            block_data = data[position : position + block_length]

            # Enhanced Packet Block (Type 0x00000006)
            if block_type == 6 and len(block_data) >= 28:
                cap_length, packet_length = struct.unpack("<II", block_data[20:28])
                packet_bytes = block_data[28 : 28 + cap_length]

                if len(packet_bytes) >= 27:
                    urb_header_length = packet_bytes[0]
                    if urb_header_length in (27, 28, 64) and len(packet_bytes) > urb_header_length:
                        urb_header = packet_bytes[:urb_header_length]
                        payload = packet_bytes[urb_header_length:]
                        endpoint = urb_header[21]
                        if len(payload) >= 8:
                            reports.append((endpoint, payload))
            position += block_length

    # 2. Legacy PCAP Format (Magic: 0xA1B2C3D4 or 0xD4C3B2A1)
    elif data.startswith(b"\xa1\xb2\xc3\xd4") or data.startswith(b"\xd4\xc3\xb2\xa1"):
        # The magic is 0xA1B2C3D4; stored little-endian it reads d4 c3 b2 a1 on disk.
        endian = "<" if data.startswith(b"\xd4\xc3\xb2\xa1") else ">"
        position = 24  # Skip Global Header
        while position + 16 <= len(data):
            header = data[position : position + 16]
            incl_len, orig_len = struct.unpack(f"{endian}II", header[8:16])
            position += 16
            if position + incl_len > len(data):
                break
            packet_bytes = data[position : position + incl_len]
            position += incl_len
            if len(packet_bytes) >= 27:
                urb_header_length = packet_bytes[0]
                if urb_header_length in (27, 28, 64) and len(packet_bytes) > urb_header_length:
                    urb_header = packet_bytes[:urb_header_length]
                    payload = packet_bytes[urb_header_length:]
                    endpoint = urb_header[21]
                    if len(payload) >= 8:
                        reports.append((endpoint, payload))

    return reports


def decode_pcap_reports(reports: List[Tuple[int, bytes]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Decodes USB IN reports into structured session metadata and downloaded oximetry records using 30-byte stream units."""
    sessions_meta = []
    samples = []
    current_timestamp = None
    sample_index = 0

    # 1. Extract 0xEC session metadata index reports
    for endpoint, report in reports:
        if report[0] == 0xEC and len(report) >= 16:
            try:
                session_list = Parsers.parse_session_index(report)
                for session in session_list:
                    sessions_meta.append({
                        "session_id": session.session_id,
                        "timestamp": session.timestamp.isoformat() if session.timestamp else None,
                        "duration_text": session.duration_text,
                        "record_count": session.record_count,
                        "raw_samples": session.raw_samples,
                    })
                    if session.timestamp and current_timestamp is None:
                        current_timestamp = session.timestamp
            except Exception:
                pass

    # 2. Assemble continuous serial byte stream from Endpoint 0x81 / 0x01 HID IN payloads
    buffer = SerialByteStreamBuffer()
    for endpoint, report in reports:
        if endpoint in (0x81, 0x01):
            buffer.write(report)

    base_timestamp = current_timestamp or datetime.now()

    # 3. Decode 30-byte stream units using SerialPacketDetector
    events = SerialPacketDetector.detect_and_decode_stream(buffer, base_timestamp=base_timestamp)

    active_spo2 = None
    active_heart_rate = None
    active_flags = "0x00"

    for event in events:
        if event.packet_type == "STORED_BLOCK":
            # Skip probe-out / dummy filler patterns on seq=0 header blocks
            is_dummy_probeout = event.sequence == 0 and (
                (event.spo2 == 99 and event.heart_rate == 95) or
                (event.spo2 == 95 and event.heart_rate == 64) or
                ((event.status_flags & 0x0F) == 0x0F) or
                ("probe-out" in (event.status_text or "").lower()) or
                ("searching" in (event.status_text or "").lower())
            )
            if is_dummy_probeout:
                continue

            if event.spo2 is not None:
                active_spo2 = event.spo2
            if event.heart_rate is not None:
                active_heart_rate = event.heart_rate
            if event.status_text:
                active_flags = event.status_text

            sample_index += 1
            timestamp = (base_timestamp + timedelta(seconds=sample_index - 1)).isoformat()

            spo2_valid = active_spo2 is not None and 30 <= active_spo2 <= 100
            heart_rate_valid = active_heart_rate is not None and 25 <= active_heart_rate <= 250
            status = "ok" if (spo2_valid and heart_rate_valid) else "probe-out"

            samples.append({
                "index": sample_index,
                "block_id": event.block_id,
                "sequence": event.sequence,
                "timestamp": timestamp,
                "spo2": active_spo2,
                "heart_rate": active_heart_rate,
                "ppg_wave": event.ppg_wave,
                "status_flags": active_flags,
                "status": status,
            })

    return sessions_meta, samples


def print_summary(filepath: str, reports_count: int, sessions: List[Dict[str, Any]], samples: List[Dict[str, Any]]):
    valid = [sample for sample in samples if sample["status"] == "ok"]
    invalid = len(samples) - len(valid)
    spo2_values = [sample["spo2"] for sample in valid]
    heart_rate_values = [sample["heart_rate"] for sample in valid]

    print(f"\n{'='*58}")
    print("  PO-400 / CMS-60D Stored Session PCAP Decoder")
    print(f"{'='*58}")
    print(f"  File            : {os.path.basename(filepath)}")
    print(f"  File Size       : {os.path.getsize(filepath):,} bytes")
    print(f"  USB IN Reports  : {reports_count:,} packets")
    print(f"  Sessions Found  : {len(sessions)}")
    for index, session in enumerate(sessions, 1):
        print(f"    [{index}] Session #{session['session_id']}: Start={session['timestamp']} | Duration={session['duration_text']} | Records={session['record_count']}")
    print(f"  Downloaded Blocks: {len(samples):,} (ok={len(valid)}, probe-out={invalid})")
    if valid:
        print(f"  SpO2 Min/Avg/Max: {min(spo2_values)}% / {sum(spo2_values)/len(spo2_values):.1f}% / {max(spo2_values)}%")
        print(f"  HR   Min/Avg/Max: {min(heart_rate_values)} / {sum(heart_rate_values)/len(heart_rate_values):.1f} / {max(heart_rate_values)} bpm")
    print(f"{'='*58}\n")


def write_csv(samples: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["index", "block_id", "sequence", "timestamp", "spo2", "heart_rate", "ppg_wave", "status_flags", "status"]
        )
        writer.writeheader()
        writer.writerows(samples)
    print(f"✅ CSV saved to: {os.path.abspath(output_path)}")


def write_json(sessions: List[Dict[str, Any]], samples: List[Dict[str, Any]], output_path: str):
    output = {
        "sessions": sessions,
        "sample_count": len(samples),
        "samples": samples,
    }
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)
    print(f"✅ JSON saved to: {os.path.abspath(output_path)}")


def main():
    parser = argparse.ArgumentParser(
        prog="decode_pcap",
        description="Decode PO-400 / CMS-60D USB HID packet capture (.pcap / .pcapng) download files.",
    )
    parser.add_argument("file", help="Path to .pcap or .pcapng file to decode.")
    parser.add_argument("-o", "--output", help="Output file path (default: input name with extension).")
    parser.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (default: csv).")
    parser.add_argument("--no-invalid", action="store_true", help="Exclude probe-out / invalid samples from output.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress summary printout.")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"❌ File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    reports = parse_pcap_file(args.file)
    if not reports:
        print(f"⚠️ No USB HID IN reports found in {args.file}", file=sys.stderr)
        sys.exit(1)

    sessions, samples = decode_pcap_reports(reports)

    if args.no_invalid:
        samples = [sample for sample in samples if sample["status"] == "ok"]

    if not args.quiet:
        print_summary(args.file, len(reports), sessions, samples)

    output_extension = "." + args.format
    output_path = args.output or (os.path.splitext(args.file)[0] + output_extension)

    if args.format == "csv":
        write_csv(samples, output_path)
    else:
        write_json(sessions, samples, output_path)


if __name__ == "__main__":
    main()
