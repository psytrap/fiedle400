"""Oximetry plotting helper tool for Pulsox PO-400.

Generates high-resolution PNG graphs of pulse oximetry recording sessions
from .spo2, .csv, and .json files.
"""

import argparse
import csv
import glob
import json
import os
import struct
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Use Agg backend for reliable headless rendering across all platforms
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def read_spo2_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a Contec .SpO2 binary file into start datetime and sample records."""
    with open(filepath, "rb") as f:
        data = f.read()

    if len(data) < 1084:
        raise ValueError(f"File too small ({len(data)} bytes, expected >= 1084)")

    magic = struct.unpack_from("<I", data, 0x0000)[0]
    if magic != 0x0358:
        raise ValueError(f"Invalid .SpO2 magic number: 0x{magic:08X} (expected 0x00000358)")

    year, month, day, hour, minute, second, count = struct.unpack_from("<7I", data, 0x0420)
    try:
        start_dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        start_dt = datetime.now()

    payload = data[1084:]
    actual_samples = min(count, len(payload) // 2)

    records = []
    for i in range(actual_samples):
        s_raw = payload[i * 2]
        h_raw = payload[i * 2 + 1]

        spo2_valid = 1 <= s_raw <= 100
        hr_valid = 1 <= h_raw <= 250
        is_ok = spo2_valid and hr_valid

        records.append({
            "timestamp": start_dt + timedelta(seconds=i),
            "spo2": float(s_raw) if spo2_valid else float("nan"),
            "heart_rate": float(h_raw) if hr_valid else float("nan"),
            "valid": is_ok,
        })

    return start_dt, records


def read_csv_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a PO-400 CSV recording file."""
    records = []
    start_dt = None

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            ts_str = row.get("timestamp") or row.get("time")
            cur_dt = None
            if ts_str:
                try:
                    cur_dt = datetime.fromisoformat(ts_str)
                except ValueError:
                    pass

            if cur_dt and start_dt is None:
                start_dt = cur_dt

            s_val = row.get("spo2")
            h_val = row.get("heart_rate") or row.get("pulse") or row.get("pr")

            try:
                spo2_num = float(s_val) if s_val not in (None, "", "None") else float("nan")
            except ValueError:
                spo2_num = float("nan")

            try:
                hr_num = float(h_val) if h_val not in (None, "", "None") else float("nan")
            except ValueError:
                hr_num = float("nan")

            if spo2_num < 1 or spo2_num > 100:
                spo2_num = float("nan")
            if hr_num < 1 or hr_num > 250:
                hr_num = float("nan")

            records.append({
                "timestamp": cur_dt,
                "spo2": spo2_num,
                "heart_rate": hr_num,
                "valid": (spo2_num == spo2_num and hr_num == hr_num),
            })

    if not start_dt:
        start_dt = datetime.now()

    # Assign sequential timestamps if missing
    for i, r in enumerate(records):
        if r["timestamp"] is None:
            r["timestamp"] = start_dt + timedelta(seconds=i)

    return start_dt, records


def read_json_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Parse a PO-400 JSON recording file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_list = data.get("samples", data) if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        raise ValueError(f"Unexpected JSON format in {filepath}")

    records = []
    start_dt = None
    if isinstance(data, dict) and "session" in data and data["session"].get("start_time"):
        try:
            start_dt = datetime.fromisoformat(data["session"]["start_time"])
        except ValueError:
            pass

    for i, item in enumerate(raw_list):
        ts_str = item.get("timestamp")
        cur_dt = None
        if ts_str:
            try:
                cur_dt = datetime.fromisoformat(ts_str)
            except ValueError:
                pass
        if cur_dt and start_dt is None:
            start_dt = cur_dt

        s_val = item.get("spo2")
        h_val = item.get("heart_rate") or item.get("pulse") or item.get("pr")

        spo2_num = float(s_val) if s_val is not None and 1 <= s_val <= 100 else float("nan")
        hr_num = float(h_val) if h_val is not None and 1 <= h_val <= 250 else float("nan")

        records.append({
            "timestamp": cur_dt,
            "spo2": spo2_num,
            "heart_rate": hr_num,
            "valid": (spo2_num == spo2_num and hr_num == hr_num),
        })

    if not start_dt:
        start_dt = datetime.now()

    for i, r in enumerate(records):
        if r["timestamp"] is None:
            r["timestamp"] = start_dt + timedelta(seconds=i)

    return start_dt, records


def load_session_file(filepath: str) -> Tuple[datetime, List[Dict[str, Any]]]:
    """Load recording session from .spo2, .csv, or .json file."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".spo2", ""):
        return read_spo2_file(filepath)
    elif ext == ".csv":
        return read_csv_file(filepath)
    elif ext == ".json":
        return read_json_file(filepath)
    else:
        # Attempt to inspect first bytes for .SpO2 magic
        try:
            return read_spo2_file(filepath)
        except Exception:
            raise ValueError(f"Unsupported file format '{ext}' for {filepath}")


def find_latest_session_file(search_dir: str = ".") -> Optional[str]:
    """Find the most recently modified recording session file in search_dir."""
    candidates = []
    for pattern in ("*.spo2", "*.SpO2", "*.csv", "*.json"):
        candidates.extend(glob.glob(os.path.join(search_dir, pattern)))

    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def plot_session(
    filepath: Optional[str] = None,
    output_png: Optional[str] = None,
    dpi: int = 150,
) -> str:
    """Generate a dual-axis SpO2 & Pulse Rate PNG chart from a recording session.

    Args:
        filepath: Input recording file (.spo2, .csv, or .json). If None, finds latest in current directory.
        output_png: Destination path for the PNG plot. If None, saved as <input_basename>.png.
        dpi: Image resolution in dots per inch (default: 150 DPI).

    Returns:
        str: Absolute path of the generated PNG file.
    """
    if not filepath:
        latest = find_latest_session_file(".") or find_latest_session_file("output")
        if not latest:
            raise FileNotFoundError("No session files (.spo2, .csv, .json) found in current directory.")
        filepath = latest

    start_dt, records = load_session_file(filepath)
    if not records:
        raise ValueError(f"Recording file {filepath} contains 0 sample records.")

    timestamps = [r["timestamp"] for r in records]
    spo2_vals = [r["spo2"] for r in records]
    hr_vals = [r["heart_rate"] for r in records]

    # Calculate statistics from valid readings
    valid_spo2 = [s for s in spo2_vals if s == s]  # non-NaN
    valid_hr = [h for h in hr_vals if h == h]

    total_duration = timedelta(seconds=len(records))
    valid_count = len(valid_spo2)
    invalid_count = len(records) - valid_count

    spo2_min = min(valid_spo2) if valid_spo2 else 0.0
    spo2_avg = sum(valid_spo2) / len(valid_spo2) if valid_spo2 else 0.0
    spo2_max = max(valid_spo2) if valid_spo2 else 0.0
    desat_count = sum(1 for s in valid_spo2 if s < 90)

    hr_min = min(valid_hr) if valid_hr else 0.0
    hr_avg = sum(valid_hr) / len(valid_hr) if valid_hr else 0.0
    hr_max = max(valid_hr) if valid_hr else 0.0

    # Determine output PNG path
    if not output_png:
        base_name, _ = os.path.splitext(filepath)
        output_png = f"{base_name}.png"

    output_path = os.path.abspath(output_png)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Styling setup
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, (ax_spo2, ax_hr) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [1.1, 1]})

    color_spo2 = "#1f77b4"      # Medical blue
    color_spo2_fill = "#aec7e8"
    color_hr = "#d62728"        # Heart rate red
    color_hr_fill = "#ff9896"

    # 1. Top Subplot: SpO2 %
    ax_spo2.plot(timestamps, spo2_vals, color=color_spo2, linewidth=1.5, label=f"SpO2 (Avg {spo2_avg:.1f}%)")
    ax_spo2.fill_between(timestamps, spo2_vals, 85, color=color_spo2_fill, alpha=0.35)

    # Reference lines
    ax_spo2.axhline(95, color="#2ca02c", linestyle="--", linewidth=1.0, alpha=0.75, label="Normal Threshold (95%)")
    ax_spo2.axhline(90, color="#d62728", linestyle=":", linewidth=1.5, alpha=0.85, label="Hypoxemia Alert (90%)")

    spo2_y_min = max(70, min(spo2_min - 3, 88) if valid_spo2 else 70)
    ax_spo2.set_ylim(spo2_y_min, 102)
    ax_spo2.set_ylabel("SpO2 (%)", fontsize=11, fontweight="bold", color=color_spo2)
    ax_spo2.set_title(
        f"Pulsox PO-400 Recording — {os.path.basename(filepath)}\n"
        f"Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}  |  Duration: {total_duration}  |  Samples: {len(records):,}",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax_spo2.legend(loc="lower left", frameon=True, fontsize=9)
    ax_spo2.grid(True, linestyle="--", alpha=0.5)

    # 2. Bottom Subplot: Pulse Rate BPM
    ax_hr.plot(timestamps, hr_vals, color=color_hr, linewidth=1.4, label=f"Heart Rate (Avg {hr_avg:.1f} bpm)")
    ax_hr.fill_between(timestamps, hr_vals, max(30, hr_min - 5) if valid_hr else 40, color=color_hr_fill, alpha=0.3)

    # Reference lines (Normal resting range: 60 - 100 bpm)
    ax_hr.axhline(100, color="#ff7f0e", linestyle="--", linewidth=1.0, alpha=0.6, label="Tachycardia Ref (100 bpm)")
    ax_hr.axhline(60, color="#17becf", linestyle="--", linewidth=1.0, alpha=0.6, label="Bradycardia Ref (60 bpm)")

    hr_y_min = max(35, hr_min - 8) if valid_hr else 40
    hr_y_max = min(220, hr_max + 10) if valid_hr else 120
    ax_hr.set_ylim(hr_y_min, hr_y_max)
    ax_hr.set_ylabel("Pulse Rate (BPM)", fontsize=11, fontweight="bold", color=color_hr)
    ax_hr.set_xlabel("Time (HH:MM:SS)", fontsize=11, fontweight="bold")
    ax_hr.legend(loc="upper left", frameon=True, fontsize=9)
    ax_hr.grid(True, linestyle="--", alpha=0.5)

    # Format X-axis date/time
    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax_hr.xaxis.set_major_locator(locator)
    ax_hr.xaxis.set_major_formatter(formatter)

    # Statistical summary watermark box on top right
    stats_text = (
        f"SUMMARY METRICS\n"
        f"─────────────────────\n"
        f"SpO2 Min : {spo2_min:.0f}%\n"
        f"SpO2 Avg : {spo2_avg:.1f}%\n"
        f"SpO2 Max : {spo2_max:.0f}%\n"
        f"SpO2 <90%: {desat_count} s\n"
        f"─────────────────────\n"
        f"HR Min   : {hr_min:.0f} bpm\n"
        f"HR Avg   : {hr_avg:.1f} bpm\n"
        f"HR Max   : {hr_max:.0f} bpm\n"
        f"Dropouts : {invalid_count} s"
    )
    ax_spo2.text(
        0.985,
        0.05,
        stats_text,
        transform=ax_spo2.transAxes,
        fontsize=8.5,
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#cccccc", alpha=0.9),
        family="monospace",
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        prog="fiedle400-plot",
        description="Generate high-resolution PNG graph from Pulsox PO-400 .SpO2, .csv, or .json recording files.",
    )
    parser.add_argument("file", nargs="?", help="Path to recording file (.spo2, .csv, or .json). Defaults to latest in output/.")
    parser.add_argument("-o", "--output", help="Output PNG file path (default: output/<filename>.png).")
    parser.add_argument("--dpi", type=int, default=150, help="Resolution in DPI (default: 150).")
    args = parser.parse_args()

    try:
        saved_path = plot_session(filepath=args.file, output_png=args.output, dpi=args.dpi)
        print(f"📊 Successfully generated session plot: {saved_path}")
    except Exception as e:
        print(f"❌ Error generating plot: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
