"""Pulsox PO-400 Command-Line Interface (CLI).

Commands:
  info     - Read hardware model, firmware version, and USB descriptors.
  sessions - List all stored recording sessions on device (v2.0.0).
  download - Extract recorded sessions from device and save to CSV or JSON.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from po400 import protocol, serial_engine
from po400.protocol import Commands, Parsers
from po400.hid_driver import PulsoxHidDevice, get_usb_sysfs_info


def command_detect(args) -> int:
    """Handler for 'detect' subcommand to run live Serial Packet Detector & Decoder."""
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    print("==================================================")
    print("  PO-400 SERIAL PACKET DETECTOR & DECODER ENGINE")
    print("==================================================")
    print(f"Connected to {node_path}...")
    print("Listening for HID report packets... (Press Ctrl+C to stop)\n")

    count = 0
    try:
        while True:
            events = engine.read_packets()
            for ev in events:
                count += 1
                spo2_str = f"{ev.spo2}%" if ev.spo2 else "N/A"
                hr_str = f"{ev.heart_rate} bpm" if ev.heart_rate else "N/A"
                print(f"[{count:04d}] Type={ev.packet_type:<15} | SpO2={spo2_str:<6} | HR={hr_str:<8} | Status={ev.status_str}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nPacket detector stopped by user.")
    finally:
        dev.close()

    return 0


def _discover_sessions_to_download(dev, download_all: bool, target_session: int, debug: bool = False) -> List[protocol.SessionInfo]:
    """Helper to discover available SessionInfo objects for download using SerialDeviceEngine."""
    engine = serial_engine.SerialDeviceEngine(dev)
    session_list = engine.list_sessions(debug=debug)

    if not download_all and target_session > 0:
        matched = [s for s in session_list if s.session_id == target_session]
        if matched:
            s = matched[0]
            print(f"Discovered Session #{target_session} metadata: Duration={s.duration_str}, Timestamp={s.timestamp}")
            return [s]
        else:
            print(f"Target Session #{target_session} not found in index table; using default bounds...")
            return [protocol.SessionInfo(session_id=target_session, user_id=1, record_count=60, duration_sec=60)]

    if not session_list:
        print("No active session table returned; defaulting to downloading Session #1...")
        return [protocol.SessionInfo(session_id=1, user_id=1, record_count=60, duration_sec=60)]

    sess_ids = [s.session_id for s in session_list]
    print(f"Found {len(session_list)} sessions to download: {sess_ids}")
    return session_list


def _download_single_session(dev, sess_info: protocol.SessionInfo, timeout_limit: float, debug: bool = False) -> List[dict]:
    """Helper to extract stored records for a single session ID using SerialDeviceEngine."""
    sess_id = sess_info.session_id
    dur_str = sess_info.duration_str
    print(f"\n---> Requesting Session #{sess_id} Data Blocks ({dur_str})...")

    engine = serial_engine.SerialDeviceEngine(dev)
    return engine.download_session(sess_info, debug=debug)



def _export_records_to_file(records: List[dict], output_filename: Optional[str], fmt: str) -> str:
    """Helper to save extracted records into CSV or JSON format."""
    if not output_filename:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"po400_all_sessions_{timestamp_str}.{fmt}"

    if fmt == "csv":
        with open(output_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["session_id", "user_id", "block_id", "seq", "timestamp", "spo2", "heart_rate", "flags"],
                extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(records)
    else:  # json
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    return os.path.abspath(output_filename)


def command_download(args):
    """Handler for 'download' subcommand using SerialDeviceEngine."""
    download_all = args.all or args.session == 0
    verbose_level = getattr(args, "verbose", 0)

    dump_path = None
    if getattr(args, "dump", None) is not None:
        if args.dump == "auto":
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            dump_path = f"po400_download_{ts_str}.dump"
        else:
            dump_path = args.dump
    
    print("Connecting to Pulsox PO-400 to extract recording data...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    total_records = []
    try:
        total_records = engine.download_all_sessions(
            target_session=args.session,
            download_all=download_all,
            timeout_override=args.timeout,
            debug=verbose_level,
            dump_file=dump_path,
        )
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    finally:
        dev.close()

    print(f"\nDownload complete. Total records collected across all sessions: {len(total_records)}")
    saved_path = _export_records_to_file(total_records, args.output, args.format.lower())
    print(f"✅ Saved all session recordings to: {saved_path}")
    if dump_path:
        print(f"🔍 Saved diagnostic raw HID frame dump to: {os.path.abspath(dump_path)}")
    return 0





def command_sessions(args):
    """Handler for 'sessions' subcommand to query session index table using SerialDeviceEngine."""
    print("Connecting to Pulsox PO-400 to query recorded session index...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    try:
        sessions = engine.list_sessions(debug=getattr(args, "verbose", 0))
    except KeyboardInterrupt:
        print("\nSession query interrupted by user.")
        return 1
    finally:
        dev.close()


    print(f"\n==================================================")
    print(f"  PULSOX PO-400 STORED RECORDING SESSIONS (v2.0.0)")
    print(f"==================================================")

    if not sessions:
        print("No stored recording sessions found in device memory.")
        print("(Note: To record a session, set Record=ON in PO-400 menu while measuring).")
    else:
        print(f"{'Session ID':<12} | {'User':<6} | {'Records':<10} | {'Duration':<12} | {'Timestamp':<20}")
        print("-" * 73)
        for s in sessions:
            ts_str = s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "N/A"
            print(f"{s.session_id:<12} | {s.user_id:<6} | {s.record_count:<10} | {s.duration_str:<12} | {ts_str:<20}")
        print(f"\nTotal sessions found: {len(sessions)}")

    return 0


def command_clear(args):
    """Handler for 'clear' subcommand to delete stored recording sessions."""
    sess_id = args.session
    target_str = f"Session #{sess_id}" if sess_id > 0 else "ALL stored recording sessions"
    
    if not args.yes:
        confirm = input(f"⚠️ Are you sure you want to permanently DELETE {target_str} from device memory? [y/N]: ")
        if confirm.lower() not in ["y", "yes"]:
            print("Operation cancelled.")
            return 0

    print(f"Connecting to Pulsox PO-400 to delete {target_str}...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    try:
        engine.clear_memory(session_id=sess_id, debug=getattr(args, "verbose", 0))
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    finally:
        dev.close()

    print(f"✅ Successfully cleared {target_str} from device flash memory.")
    return 0


def command_read_time(args):
    """Handler for 'read-time' subcommand to read active device RTC timestamp using SerialDeviceEngine."""
    print("Connecting to Pulsox PO-400 to read Real-Time Clock (RTC)...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    try:
        rtc_dt = engine.read_rtc_time(debug=getattr(args, "verbose", 0))

        if rtc_dt:
            ts_str = rtc_dt.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🕒 Device RTC Clock Timestamp: {ts_str}")
            print(f"   Command format: python3 -m po400.cli set-time \"{ts_str}\"")
        else:
            print("\n🕒 Device RTC Clock Timestamp: Unreported or Default Crystal Clock")

    except KeyboardInterrupt:
        print("\nRead RTC interrupted by user.")
    finally:
        dev.close()
    return 0


def command_set_time(args):
    """Handler for 'set-time' subcommand to set device RTC timestamp using SerialDeviceEngine."""
    if hasattr(args, "timestamp") and args.timestamp:
        try:
            target_dt = datetime.fromisoformat(args.timestamp.replace(" ", "T"))
        except ValueError:
            print(f"❌ Error: Invalid timestamp format '{args.timestamp}'. Expected 'YYYY-MM-DD HH:MM:SS'.")
            return 1
    else:
        target_dt = datetime.now()

    ts_str = target_dt.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Connecting to Pulsox PO-400 to set Real-Time Clock (RTC)...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    engine = serial_engine.SerialDeviceEngine(dev)
    try:
        print(f"Sending Set-RTC command (0x83) for timestamp: {ts_str}...")
        engine.set_rtc_time(target_dt, debug=getattr(args, "verbose", 0))
        print("Received device ACK: Real-Time Clock synchronized!")

    except KeyboardInterrupt:
        print("\nSet RTC interrupted by user.")
    finally:
        dev.close()

    print(f"✅ Successfully set PO-400 device clock to: {ts_str}")
    print(f"   Command format: python3 -m po400.cli set-time \"{ts_str}\"")
    return 0


def command_info(args):
    """Handler for 'info' subcommand to read hardware and firmware information."""
    print("Connecting to Pulsox PO-400 to read device information...")
    try:
        dev = PulsoxHidDevice(dev_path=getattr(args, "device", None), backend=getattr(args, "backend", None))
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    meta = dev.get_descriptor_info()
    engine = serial_engine.SerialDeviceEngine(dev)
    try:
        res = engine.read_device_info(debug=getattr(args, "verbose", 0))
        info = res["device_info"]
        active_user_id = res["active_user_id"]
        rtc_time_str = res["rtc_time_str"]
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
        return 1
    finally:
        dev.close()

    backend_label = "Linux hidraw (native)" if dev.backend_name == "hidraw" else "hid (cross-platform)"

    readable, writable = True, True
    if node_path.startswith("/dev/"):
        readable = os.access(node_path, os.R_OK)
        writable = os.access(node_path, os.W_OK)

    vid_hex = meta.get("vid_hex", "28E9")
    pid_hex = meta.get("pid_hex", "028A")
    decoded_model, model_source = protocol.decode_usb_vid_pid(vid_hex, pid_hex)

    fw_str = info.firmware_version if (info and info.firmware_version) else "v2.0 (CMS-60D/PO-400 v2)"
    sn_str = info.serial_number if (info and info.serial_number) else "50F"
    up_str = info.user_profile if (info and info.user_profile) else "user"
    geom_str = info.flash_geometry if (info and info.flash_geometry) else "112 Bytes Sub-chunk Payload"

    print(f"\n==================================================")
    print(f"  PULSOX PO-400 DEVICE & HARDWARE INFORMATION")
    print(f"==================================================")
    print(f"  Device Path / Node     : {node_path}")
    print(f"  Active HID Backend     : {backend_label}")
    print(f"  Hardware Model         : {decoded_model}")
    print(f"  └─ Provenance Source   : [{model_source}]")
    print(f"  USB Vendor:Product ID  : {vid_hex}:{pid_hex}")
    print(f"  USB Product Name       : {meta.get('product') or 'N/A (Not reported in USB descriptor)'}")
    print(f"  USB Manufacturer       : {meta.get('manufacturer') or 'N/A (Not reported in USB descriptor)'}")
    if meta.get("serial_number"):
        print(f"  USB Serial Descriptor  : {meta['serial_number']}")
    if meta.get("release_number"):
        print(f"  USB Hardware Release   : {meta['release_number']}")
    if meta.get("bus_path"):
        print(f"  USB Bus / Topology     : {meta['bus_path']}")
    print(f"  Descriptor Data Source : {meta.get('metadata_source', 'N/A')}")
    print(f"  Read/Write Access      : Readable={readable}, Writable={writable}")
    print(f"  Firmware Version       : {fw_str}")
    print(f"  Serial Number          : {sn_str}")
    print(f"  User Profile String    : {up_str}")
    print(f"  Active Session User ID : User #{active_user_id}")
    print(f"  Device RTC Timestamp   : {rtc_time_str}")
    print(f"  Storage Memory Geometry: {geom_str}")
    print(f"==================================================\n")

    return 0


def parse_session_selection(selection_str: str, available_sessions: List[protocol.SessionInfo]) -> List[protocol.SessionInfo]:
    """Parses user input into an ordered, deduplicated list of SessionInfo objects.
    
    Supports:
      - 'a', 'all': returns all available sessions
      - '1': single session ID
      - '1,3,4': comma-separated IDs
      - '1-3': inclusive range of session IDs
      - combinations: '1-3, 5, 7-8'
    """
    raw = selection_str.strip().lower()
    if not raw:
        raise ValueError("No session selected.")

    if raw in ("a", "all"):
        if not available_sessions:
            raise ValueError("No sessions available to download.")
        return list(available_sessions)

    sess_map = {s.session_id: s for s in available_sessions}
    selected_ids = []

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            bounds = [b.strip() for b in part.split("-", 1)]
            if not bounds[0].isdigit() or not bounds[1].isdigit():
                raise ValueError(f"Invalid range syntax: '{part}'")
            start_id, end_id = int(bounds[0]), int(bounds[1])
            if start_id > end_id:
                raise ValueError(f"Range start cannot exceed range end: '{part}'")
            for sid in range(start_id, end_id + 1):
                if sid not in sess_map:
                    raise ValueError(f"Session #{sid} does not exist.")
                if sid not in selected_ids:
                    selected_ids.append(sid)
        else:
            if not part.isdigit():
                raise ValueError(f"Invalid session number: '{part}'")
            sid = int(part)
            if sid not in sess_map:
                raise ValueError(f"Session #{sid} does not exist.")
            if sid not in selected_ids:
                selected_ids.append(sid)

    if not selected_ids:
        raise ValueError("No valid sessions selected.")

    return [sess_map[sid] for sid in selected_ids]


def generate_iso_filename(selected_sessions: List[protocol.SessionInfo]) -> str:
    """Generates a uniform CSV filename with ISO start and end datetimes.
    
    Format: po400_{start_iso}_{end_iso}.csv
    e.g.: po400_2026-09-06T100516_2026-09-06T105028.csv
    """
    now = datetime.now()
    valid_starts = [s.timestamp for s in selected_sessions if s.timestamp]
    start_dt = min(valid_starts) if valid_starts else now

    valid_ends = [
        (s.timestamp + timedelta(seconds=s.duration_seconds))
        for s in selected_sessions if s.timestamp
    ]
    if valid_ends:
        end_dt = max(valid_ends)
    else:
        total_sec = sum(s.duration_seconds for s in selected_sessions)
        end_dt = start_dt + timedelta(seconds=max(total_sec, 60))

    start_iso = start_dt.strftime("%Y-%m-%dT%H%M%S")
    end_iso = end_dt.strftime("%Y-%m-%dT%H%M%S")
    return f"po400_{start_iso}_{end_iso}.csv"


def run_interactive_wizard(args) -> int:
    """Interactive text-based wizard prompt when po400 is run without subcommands."""
    print("============================================================")
    print("              PULOX PO-400 INTERACTIVE WIZARD")
    print("============================================================")

    dev_path = getattr(args, "device", None)
    backend = getattr(args, "backend", None)
    verbose_level = getattr(args, "verbose", 0)

    while True:
        print("\nConnecting to device...")
        try:
            dev = PulsoxHidDevice(dev_path=dev_path, backend=backend)
            node_path = dev.connect()
            print(f"[✓] Connected to {node_path}")
        except Exception as e:
            print(f"[✗] Error connecting to device: {e}")
            return 1

        engine = serial_engine.SerialDeviceEngine(dev)
        try:
            # 1. Progressive hardware handshake & active user
            dev.write_report(Commands.unlock_handshake())
            time.sleep(0.15)
            neg_res = dev.read_report(64)
            active_user_id = Parsers.parse_user_id(neg_res) if neg_res else 1
            print(f"[✓] Hardware Handshake    : ACK (User #{active_user_id})")

            # 2. Progressive device info (model, firmware, serial)
            dev_res = engine.read_device_info(debug=verbose_level)
            info = dev_res.get("device_info", protocol.DeviceInfo())
            rtc_str = dev_res.get("rtc_time_str", "N/A")

            fw_str = info.firmware_version if info.firmware_version else "v2.0"
            sn_str = info.serial_number if info.serial_number else "50F"
            up_str = info.user_profile if info.user_profile else "user"

            print(f"[✓] Device Descriptor     : CMS-50F (Model: {sn_str})")
            print(f"[✓] Firmware Version      : {fw_str} | Serial: {sn_str}")
            print(f"[✓] Device Clock (RTC)    : {rtc_str}")
            print(f"[✓] User Profile String   : {up_str}")

            # 3. Progressive flash session discovery
            print("\nScanning flash memory for recorded sessions...")
            sessions = engine.list_sessions(debug=verbose_level)

            if not sessions:
                print("No recorded sessions found in flash memory.")
                print("\n------------------------------------------------------------")
                print("Actions:")
                print("  [C]   Clear / format device flash memory")
                print("  [Q]   Quit")
                print("------------------------------------------------------------")
                act = input("Select action [c, q]: ").strip().lower()
                if act in ("c", "clear"):
                    confirm = input("⚠️ Are you sure you want to format device flash memory? [y/N]: ").strip().lower()
                    if confirm in ("y", "yes"):
                        engine.clear_memory(0, debug=verbose_level)
                        print("✅ Device flash memory formatted successfully.")
                print("Goodbye!")
                return 0

            print(f"Found {len(sessions)} recorded session(s):")
            for s in sessions:
                ts_str = s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "N/A"
                print(f"  [{s.session_id}] {ts_str}  |  Duration: {s.duration_str} ({s.record_count:,} records)")

            print("\n------------------------------------------------------------")
            print("Actions:")
            print("  [#]   Download session(s) — e.g. single (1), list (1,3,4), or range (1-3)")
            print("  [A]   Download all sessions (a or all)")
            print("  [C]   Clear / erase device flash memory")
            print("  [Q]   Quit")
            print("------------------------------------------------------------")

            choice = input(f"Select action [1-{len(sessions)}, ranges like 1-{len(sessions)}, a, c, q]: ").strip()
            if not choice or choice.lower() in ("q", "quit", "exit"):
                print("Goodbye!")
                return 0

            if choice.lower() in ("c", "clear"):
                confirm = input("⚠️ Are you sure you want to permanently DELETE ALL recordings from device memory? [y/N]: ").strip().lower()
                if confirm in ("y", "yes"):
                    engine.clear_memory(0, debug=verbose_level)
                    print("✅ Device flash memory cleared successfully.")
                ret = input("\nReturn to main menu? [y/N]: ").strip().lower()
                if ret in ("y", "yes"):
                    continue
                print("Goodbye!")
                return 0

            # Session download selection
            try:
                selected_sessions = parse_session_selection(choice, sessions)
            except ValueError as ve:
                print(f"[!] {ve}")
                continue

            default_fn = generate_iso_filename(selected_sessions)
            fn_input = input(f"\nEnter output CSV filename [default: {default_fn}]: ").strip()
            csv_fn = fn_input if fn_input else default_fn

            all_records = []
            for idx, s in enumerate(selected_sessions, 1):
                print(f"\nDownloading Session #{s.session_id} ({idx}/{len(selected_sessions)})...")
                recs = engine.download_session(s, debug=verbose_level)
                all_records.extend(recs)

            saved_path = _export_records_to_file(all_records, csv_fn, "csv")
            print(f"\n✅ Successfully saved {len(all_records):,} records across {len(selected_sessions)} session(s) to: {saved_path}")

            # Offer flash erase with default = YES
            erase_input = input("\nErase recordings from device flash? [Y/n]: ").strip().lower()
            if erase_input in ("", "y", "yes"):
                engine.clear_memory(0, debug=verbose_level)
                print("✅ Device flash memory erased successfully.")
            else:
                print("Flash recordings preserved.")

            # Offer return to menu with default = NO
            ret_input = input("\nReturn to main menu? [y/N]: ").strip().lower()
            if ret_input in ("y", "yes"):
                continue
            else:
                print("Goodbye!")
                return 0

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return 1
        finally:
            dev.close()


def main():
    parser = argparse.ArgumentParser(
        prog="po400",
        description="CLI tool to query device information and extract recordings from Pulsox PO-400 USB HID pulse oximeter.",
    )
    parser.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser.add_argument("-b", "--backend", "--driver", dest="backend", choices=["hidraw", "hid"], default=None, help="HID driver backend: 'hidraw' (default on Linux) or 'hid' (default on Windows / Linux testing).")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: info
    parser_info = subparsers.add_parser("info", help="Read hardware model, firmware version, and USB descriptors.")
    parser_info.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_info.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_info.set_defaults(func=command_info)

    # Subcommand: sessions
    parser_sess = subparsers.add_parser("sessions", help="List all stored recording sessions on device (v2.0.0).")
    parser_sess.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_sess.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_sess.set_defaults(func=command_sessions)

    # Subcommand: download
    parser_dl = subparsers.add_parser("download", help="Download recorded sessions from device memory (defaults to ALL sessions).")
    parser_dl.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_dl.add_argument("-s", "--session", type=int, default=0, help="Specific session ID to download (default: 0 = download ALL sessions).")
    parser_dl.add_argument("-a", "--all", action="store_true", help="Download ALL stored recording sessions (default).")
    parser_dl.add_argument("-o", "--output", help="Output file path (default: po400_all_sessions_<timestamp>.csv).")
    parser_dl.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (csv or json).")
    parser_dl.add_argument("-t", "--timeout", type=int, default=0, help="Override maximum read duration per session in seconds (default: 0 = full session duration).")
    parser_dl.add_argument("--dump", nargs="?", const="auto", help="Save diagnostic raw HID frame dump file (optional custom filename).")
    parser_dl.add_argument("-v", "--verbose", "--debug", dest="verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_dl.set_defaults(func=command_download)

    # Subcommand: clear
    parser_clear = subparsers.add_parser("clear", help="Clear/delete stored recording sessions from device flash memory.")
    parser_clear.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_clear.add_argument("-s", "--session", type=int, default=0, help="Specific session ID to delete (default: 0 = delete ALL sessions).")
    parser_clear.add_argument("-y", "--yes", action="store_true", help="Bypass confirmation prompt.")
    parser_clear.set_defaults(func=command_clear)

    # Subcommand: read-time
    parser_rt = subparsers.add_parser("read-time", help="Read active device Real-Time Clock (RTC) timestamp.")
    parser_rt.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_rt.set_defaults(func=command_read_time)

    # Subcommand: set-time
    parser_st = subparsers.add_parser("set-time", help="Set device Real-Time Clock (RTC) to specified timestamp or current system time.")
    parser_st.add_argument("timestamp", nargs="?", help="Optional timestamp string 'YYYY-MM-DD HH:MM:SS' (defaults to current system time).")
    parser_st.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_st.set_defaults(func=command_set_time)

    # Subcommand: detect
    parser_det = subparsers.add_parser("detect", help="Run live Serial Packet Detector & Decoder on incoming USB HID stream.")
    parser_det.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_det.set_defaults(func=command_detect)

    for p in [parser_info, parser_sess, parser_dl, parser_clear, parser_rt, parser_st, parser_det]:
        p.add_argument("-b", "--backend", "--driver", dest="backend", choices=["hidraw", "hid"], default=argparse.SUPPRESS, help="HID driver backend: 'hidraw' (default on Linux) or 'hid' (default on Windows / Linux testing).")

    args = parser.parse_args()

    if not args.command:
        sys.exit(run_interactive_wizard(args))

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
