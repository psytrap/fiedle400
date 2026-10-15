#!/usr/bin/env python3
"""Contec .SpO2 Binary File Decoder

Decodes the proprietary binary .SpO2 format produced by Contec SpO2 Assistant
software (used by PO-400 / CMS-60D pulse oximeters).

File Format:
    Header : 1084 bytes (0x043C)
        0x0000 : uint32_le  Magic / File size hint
        0x0004 : uint32_le  File format version (0x01 = v1)
        0x0420 : uint32_le  Year
        0x0424 : uint32_le  Month
        0x0428 : uint32_le  Day
        0x042C : uint32_le  Hour
        0x0430 : uint32_le  Minute
        0x0434 : uint32_le  Second
        0x0438 : uint32_le  Total sample count (1 Hz)
    Payload: N x 2 bytes
        Byte 0 : SpO2 %       (0..100, 0 = invalid / probe-out)
        Byte 1 : Heart Rate   (0..250 bpm, 0 = invalid)

Usage:
    python3 decode_spo2.py <file.SpO2> [-f csv|json] [-o output] [--no-invalid]
"""

import argparse
import csv
import json
import os
import struct
import sys
from datetime import datetime, timedelta

HEADER_SIZE    = 0x043C   # 1084 bytes
MAGIC_OFFSET   = 0x0000
VERSION_OFFSET = 0x0004
META_OFFSET    = 0x0420   # Datetime block starts here


def parse_header(data: bytes) -> dict:
    """Parse the 1084-byte .SpO2 file header."""
    if len(data) < HEADER_SIZE:
        raise ValueError(f"File too short: {len(data)} bytes (expected >= {HEADER_SIZE})")

    magic   = struct.unpack_from("<I", data, MAGIC_OFFSET)[0]
    version = struct.unpack_from("<I", data, VERSION_OFFSET)[0]

    year   = struct.unpack_from("<I", data, 0x0420)[0]
    month  = struct.unpack_from("<I", data, 0x0424)[0]
    day    = struct.unpack_from("<I", data, 0x0428)[0]
    hour   = struct.unpack_from("<I", data, 0x042C)[0]
    minute = struct.unpack_from("<I", data, 0x0430)[0]
    second = struct.unpack_from("<I", data, 0x0434)[0]
    count  = struct.unpack_from("<I", data, 0x0438)[0]

    try:
        start_dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        start_dt = None

    return {
        "magic":        f"0x{magic:08X}",
        "version":      version,
        "start_time":   start_dt,
        "sample_count": count,
    }


def parse_samples(data: bytes, start_time, header_count: int = 0):
    """Parse the 1 Hz [SpO2, HR] payload starting at HEADER_SIZE.

    Caps output to header_count if provided (avoids reading padding bytes).
    Values SpO2>100 or HR>250 are sentinel/padding bytes and marked probe-out.
    """
    payload = data[HEADER_SIZE:]
    samples = []
    n = min(len(payload) // 2, header_count) if header_count > 0 else len(payload) // 2

    for i in range(n):
        spo2 = payload[i * 2]
        hr   = payload[i * 2 + 1]
        ts   = (start_time + timedelta(seconds=i)).isoformat() if start_time else None

        # 0 = no signal; >100 / >250 = sentinel/padding byte — all mean probe-out
        spo2_valid = 1 <= spo2 <= 100
        hr_valid   = 1 <= hr   <= 250
        status     = "ok" if (spo2_valid and hr_valid) else "probe-out"

        samples.append({
            "index":      i + 1,
            "timestamp":  ts,
            "spo2":       spo2 if spo2_valid else None,
            "heart_rate": hr   if hr_valid   else None,
            "status":     status,
        })
    return samples


def print_summary(meta, samples, filepath):
    valid   = [s for s in samples if s["status"] == "ok"]
    invalid = len(samples) - len(valid)
    spo2_vals = [s["spo2"] for s in valid]
    hr_vals   = [s["heart_rate"] for s in valid]

    print(f"\n{'='*54}")
    print(f"  Contec .SpO2 File Decoder")
    print(f"{'='*54}")
    print(f"  File            : {os.path.basename(filepath)}")
    print(f"  File Size       : {os.path.getsize(filepath):,} bytes")
    print(f"  Format Version  : {meta['version']}")
    print(f"  Session Start   : {meta['start_time'].strftime('%Y-%m-%d %H:%M:%S') if meta['start_time'] else 'N/A'}")
    print(f"  Header Count    : {meta['sample_count']:,} samples")
    print(f"  Parsed Samples  : {len(samples):,}  (ok={len(valid)}, probe-out={invalid})")
    if valid:
        print(f"  Duration        : {timedelta(seconds=len(samples))}")
        print(f"  SpO2 Min/Avg/Max: {min(spo2_vals)}% / {sum(spo2_vals)/len(spo2_vals):.1f}% / {max(spo2_vals)}%")
        print(f"  HR   Min/Avg/Max: {min(hr_vals)} / {sum(hr_vals)/len(hr_vals):.1f} / {max(hr_vals)} bpm")
    print(f"{'='*54}\n")


def write_csv(samples, output_path):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "timestamp", "spo2", "heart_rate", "status"])
        writer.writeheader()
        writer.writerows(samples)
    print(f"✅ CSV saved to: {os.path.abspath(output_path)}")


def write_json(samples, meta, output_path):
    out = {
        "session": {
            "start_time":   meta["start_time"].isoformat() if meta["start_time"] else None,
            "sample_count": meta["sample_count"],
            "version":      meta["version"],
        },
        "samples": samples,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"✅ JSON saved to: {os.path.abspath(output_path)}")


def main():
    parser = argparse.ArgumentParser(
        prog="decode_spo2",
        description="Decode Contec .SpO2 binary recording files from PO-400 / CMS-60D devices.",
    )
    parser.add_argument("file", help="Path to the .SpO2 file to decode.")
    parser.add_argument("-o", "--output", help="Output file path (default: same name as input with new extension).")
    parser.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (default: csv).")
    parser.add_argument("--no-invalid", action="store_true", help="Exclude probe-out / invalid samples from output.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress summary printout.")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"❌ File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "rb") as f:
        data = f.read()

    try:
        meta = parse_header(data)
    except ValueError as e:
        print(f"❌ Header parse error: {e}", file=sys.stderr)
        sys.exit(1)

    samples = parse_samples(data, meta["start_time"], header_count=meta["sample_count"])

    if args.no_invalid:
        samples = [s for s in samples if s["status"] == "ok"]

    if not args.quiet:
        print_summary(meta, samples, args.file)

    output_path = args.output or (os.path.splitext(args.file)[0] + "." + args.format)

    if args.format == "csv":
        write_csv(samples, output_path)
    else:
        write_json(samples, meta, output_path)


if __name__ == "__main__":
    main()
