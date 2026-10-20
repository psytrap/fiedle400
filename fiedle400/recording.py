"""Readers for recordings already on disk: .spo2, .csv and .json (T-013).

Standard library only, so `fiedle400 view` works in the zero-dependency binary.
Every reader returns records in the shape the download produces and the HTML
viewer takes: {"timestamp": ISO string, "spo2": int or None,
"heart_rate": int or None, "flags": "probe-out" or None}, one per second.
A value outside the valid range (SpO2 1-100 %, pulse 1-250 bpm) becomes None;
a second with neither value is marked probe-out.
"""

import csv
import glob
import json
import os
import struct
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fiedle400.export import SPO2_HEADER_SIZE, SPO2_MAGIC, parse_record_datetime

RECORDING_EXTENSIONS = (".spo2", ".csv", ".json")


def _value(raw: Any, hi: int) -> Optional[int]:
    """`raw` as an int if it is a number in 1..hi, else None."""
    if raw is None or raw == "" or raw == "None":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v != v or not 1 <= v <= hi:  # NaN or out of range
        return None
    return int(round(v))


def _record(ts: datetime, spo2: Optional[int], hr: Optional[int]) -> Dict[str, Any]:
    return {
        "timestamp": ts.isoformat(),
        "spo2": spo2,
        "heart_rate": hr,
        "flags": "probe-out" if spo2 is None and hr is None else None,
    }


def read_spo2_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a Contec .SpO2 binary file (SPO2_FORMAT.md) into start time and records."""
    with open(filepath, "rb") as f:
        data = f.read()
    if len(data) < SPO2_HEADER_SIZE:
        raise ValueError(f"File too small ({len(data)} bytes, expected >= {SPO2_HEADER_SIZE})")
    magic = struct.unpack_from("<I", data, 0x0000)[0]
    if magic != SPO2_MAGIC:
        raise ValueError(f"Invalid .SpO2 magic number: 0x{magic:08X} (expected 0x{SPO2_MAGIC:08X})")
    year, month, day, hour, minute, second, count = struct.unpack_from("<7I", data, 0x0420)
    try:
        start_dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise ValueError(f"Invalid start time in the .SpO2 header: {year}-{month}-{day} {hour}:{minute}:{second}")
    payload = data[SPO2_HEADER_SIZE:]
    n = min(count, len(payload) // 2)
    records = [
        _record(start_dt + timedelta(seconds=i), _value(payload[2 * i], 100), _value(payload[2 * i + 1], 250))
        for i in range(n)
    ]
    return start_dt, records


def _from_rows(rows: List[Dict[str, Any]], filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Records from dict rows (CSV or JSON). A row without a usable timestamp follows
    the previous one by a second; the first row must have one, since the viewer's
    time axis would otherwise be invented."""
    records: List[Dict[str, Any]] = []
    prev: Optional[datetime] = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Unexpected record {row!r} in {filepath}")
        ts = parse_record_datetime(row.get("timestamp") or row.get("time"))
        if ts is None:
            if prev is None:
                raise ValueError(f"The first record in {filepath} has no timestamp")
            ts = prev + timedelta(seconds=1)
        prev = ts
        hr_raw = row.get("heart_rate")
        if hr_raw in (None, ""):
            hr_raw = row.get("pulse", row.get("pr"))
        records.append(_record(ts, _value(row.get("spo2"), 100), _value(hr_raw, 250)))
    if not records:
        raise ValueError(f"{filepath} contains no records")
    return parse_record_datetime(records[0]["timestamp"]), records


def read_csv_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a fiedle400 CSV export (columns timestamp, spo2, heart_rate, ...)."""
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        return _from_rows(list(csv.DictReader(f)), filepath)


def read_json_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a fiedle400 JSON export (a list of records, or {"samples": [...]})."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("samples") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Unexpected JSON format in {filepath}")
    return _from_rows(rows, filepath)


def load_session_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Load a recording from a .spo2, .csv or .json file (chosen by extension)."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        return read_csv_file(filepath)
    if ext == ".json":
        return read_json_file(filepath)
    if ext in (".spo2", ""):
        return read_spo2_file(filepath)
    raise ValueError(f"Unsupported file format '{ext}' for {filepath} (use .spo2, .csv or .json)")


def find_latest_session_file(search_dir: str = ".") -> Optional[str]:
    """The most recently modified .spo2/.csv/.json file in `search_dir`, or None."""
    candidates = {
        os.path.abspath(p)
        for p in glob.glob(os.path.join(search_dir, "*"))
        if os.path.isfile(p) and os.path.splitext(p)[1].lower() in RECORDING_EXTENSIONS
    }
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)
