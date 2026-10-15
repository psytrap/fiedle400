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
from typing import List, Dict, Any, Tuple, Optional

# Ensure the po400 package (repository root, two levels up) can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from po400.protocol import Parsers, SessionInfo
from po400.serial_engine import SerialPacketDetector, SerialByteStreamBuffer


def parse_pcap_file(filepath: str) -> List[Tuple[int, bytes]]:
    """Parses a .pcap or .pcapng file and returns raw (endpoint_id, payload_bytes) tuples."""
    with open(filepath, "rb") as f:
        data = f.read()

    reports = []
    if len(data) < 24:
        return reports

    # 1. PCAPNG Format (Section Header Block Magic: 0x0A0D0D0A)
    if data.startswith(b"\x0a\x0d\x0d\x0a"):
        pos = 0
        while pos < len(data):
            if pos + 8 > len(data):
                break
            block_type, block_len = struct.unpack("<II", data[pos : pos + 8])
            if block_len < 12 or pos + block_len > len(data):
                break
            block_data = data[pos : pos + block_len]

            # Enhanced Packet Block (Type 0x00000006)
            if block_type == 6 and len(block_data) >= 28:
                cap_len, pkt_len = struct.unpack("<II", block_data[20:28])
                pkt_bytes = block_data[28 : 28 + cap_len]

                if len(pkt_bytes) >= 27:
                    urb_hdr_len = pkt_bytes[0]
                    if urb_hdr_len in (27, 28, 64) and len(pkt_bytes) > urb_hdr_len:
                        urb_hdr = pkt_bytes[:urb_hdr_len]
                        payload = pkt_bytes[urb_hdr_len:]
                        ep = urb_hdr[21]
                        if len(payload) >= 8:
                            reports.append((ep, payload))
            pos += block_len

    # 2. Legacy PCAP Format (Magic: 0xA1B2C3D4 or 0xD4C3B2A1)
    elif data.startswith(b"\xa1\xb2\xc3\xd4") or data.startswith(b"\xd4\xc3\xb2\xa1"):
        # The magic is 0xA1B2C3D4; stored little-endian it reads d4 c3 b2 a1 on disk.
        endian = "<" if data.startswith(b"\xd4\xc3\xb2\xa1") else ">"
        pos = 24  # Skip Global Header
        while pos + 16 <= len(data):
            hdr = data[pos : pos + 16]
            incl_len, orig_len = struct.unpack(f"{endian}II", hdr[8:16])
            pos += 16
            if pos + incl_len > len(data):
                break
            pkt_bytes = data[pos : pos + incl_len]
            pos += incl_len
            if len(pkt_bytes) >= 27:
                urb_hdr_len = pkt_bytes[0]
                if urb_hdr_len in (27, 28, 64) and len(pkt_bytes) > urb_hdr_len:
                    urb_hdr = pkt_bytes[:urb_hdr_len]
                    payload = pkt_bytes[urb_hdr_len:]
                    ep = urb_hdr[21]
                    if len(payload) >= 8:
                        reports.append((ep, payload))

    return reports


def decode_pcap_reports(reports: List[Tuple[int, bytes]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Decodes USB IN reports into structured session metadata and downloaded oximetry records using 30-byte stream units."""
    sessions_meta = []
    samples = []
    current_timestamp = None
    sample_index = 0

    # 1. Extract 0xEC session metadata index reports
    for ep, r in reports:
        if r[0] == 0xEC and len(r) >= 16:
            try:
                sess_list = Parsers.parse_session_index(r)
                for s in sess_list:
                    sessions_meta.append({
                        "session_id": s.session_id,
                        "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                        "duration_str": s.duration_str,
                        "record_count": s.record_count,
                    })
                    if s.timestamp and current_timestamp is None:
                        current_timestamp = s.timestamp
            except Exception:
                pass

    # 2. Assemble continuous serial byte stream from Endpoint 0x81 / 0x01 HID IN payloads
    buf = SerialByteStreamBuffer()
    for ep, r in reports:
        if ep in (0x81, 0x01):
            buf.write(r)

    base_ts = current_timestamp or datetime.now()

    # 3. Decode 30-byte stream units using SerialPacketDetector
    events = SerialPacketDetector.detect_and_decode_stream(buf, base_timestamp=base_ts)

    active_spo2 = None
    active_hr = None
    active_flags = "0x00"

    for ev in events:
        if ev.packet_type == "STORED_BLOCK":
            # Skip probe-out / dummy filler patterns on seq=0 header blocks
            is_dummy_probeout = ev.seq == 0 and (
                (ev.spo2 == 99 and ev.heart_rate == 95) or
                (ev.spo2 == 95 and ev.heart_rate == 64) or
                ((ev.status_flags & 0x0F) == 0x0F) or
                ("probe-out" in (ev.status_str or "").lower()) or
                ("searching" in (ev.status_str or "").lower())
            )
            if is_dummy_probeout:
                continue

            if ev.spo2 is not None:
                active_spo2 = ev.spo2
            if ev.heart_rate is not None:
                active_hr = ev.heart_rate
            if ev.status_str:
                active_flags = ev.status_str

            sample_index += 1
            ts = (base_ts + timedelta(seconds=sample_index - 1)).isoformat()

            spo2_valid = active_spo2 is not None and 30 <= active_spo2 <= 100
            hr_valid = active_hr is not None and 25 <= active_hr <= 250
            status = "ok" if (spo2_valid and hr_valid) else "probe-out"

            samples.append({
                "index": sample_index,
                "block_id": ev.block_id,
                "seq": ev.seq,
                "timestamp": ts,
                "spo2": active_spo2,
                "heart_rate": active_hr,
                "ppg_wave": ev.ppg_wave,
                "status_flags": active_flags,
                "status": status,
            })

    return sessions_meta, samples


def print_summary(filepath: str, reports_cnt: int, sessions: List[Dict[str, Any]], samples: List[Dict[str, Any]]):
    valid = [s for s in samples if s["status"] == "ok"]
    invalid = len(samples) - len(valid)
    spo2_vals = [s["spo2"] for s in valid]
    hr_vals = [s["heart_rate"] for s in valid]

    print(f"\n{'='*58}")
    print(f"  PO-400 / CMS-60D Stored Session PCAP Decoder")
    print(f"{'='*58}")
    print(f"  File            : {os.path.basename(filepath)}")
    print(f"  File Size       : {os.path.getsize(filepath):,} bytes")
    print(f"  USB IN Reports  : {reports_cnt:,} packets")
    print(f"  Sessions Found  : {len(sessions)}")
    for idx, sess in enumerate(sessions, 1):
        print(f"    [{idx}] Session #{sess['session_id']}: Start={sess['timestamp']} | Duration={sess['duration_str']} | Records={sess['record_count']}")
    print(f"  Downloaded Blocks: {len(samples):,} (ok={len(valid)}, probe-out={invalid})")
    if valid:
        print(f"  SpO2 Min/Avg/Max: {min(spo2_vals)}% / {sum(spo2_vals)/len(spo2_vals):.1f}% / {max(spo2_vals)}%")
        print(f"  HR   Min/Avg/Max: {min(hr_vals)} / {sum(hr_vals)/len(hr_vals):.1f} / {max(hr_vals)} bpm")
    print(f"{'='*58}\n")


def write_csv(samples: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["index", "block_id", "seq", "timestamp", "spo2", "heart_rate", "ppg_wave", "status_flags", "status"]
        )
        writer.writeheader()
        writer.writerows(samples)
    print(f"✅ CSV saved to: {os.path.abspath(output_path)}")


def write_json(sessions: List[Dict[str, Any]], samples: List[Dict[str, Any]], output_path: str):
    out = {
        "sessions": sessions,
        "sample_count": len(samples),
        "samples": samples,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
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
        samples = [s for s in samples if s["status"] == "ok"]

    if not args.quiet:
        print_summary(args.file, len(reports), sessions, samples)

    output_ext = "." + args.format
    output_path = args.output or (os.path.splitext(args.file)[0] + output_ext)

    if args.format == "csv":
        write_csv(samples, output_path)
    else:
        write_json(sessions, samples, output_path)


if __name__ == "__main__":
    main()
