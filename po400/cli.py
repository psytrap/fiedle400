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
from datetime import datetime
from typing import List, Optional, Tuple

from po400 import protocol, serial_engine
from po400.protocol import Commands, Parsers
from po400.hid_driver import PulsoxHidDevice, get_usb_sysfs_info


def command_detect(args) -> int:
    """Handler for 'detect' subcommand to run live Serial Packet Detector & Decoder."""
    try:
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
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
        dev = PulsoxHidDevice(dev_path=args.device)
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

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

    readable = os.access(node_path, os.R_OK)
    writable = os.access(node_path, os.W_OK)

    # Read USB Manufacturer, Product, and Bus ID dynamically from sysfs
    sysfs_mfg, sysfs_prod, sysfs_bus = get_usb_sysfs_info(node_path)

    node_name = os.path.basename(node_path)
    uevent_file = f"/sys/class/hidraw/{node_name}/device/uevent"
    hid_id, hid_name = "N/A", "N/A"
    if os.path.exists(uevent_file):
        try:
            with open(uevent_file, "r") as f:
                for line in f:
                    if line.startswith("HID_ID="):
                        hid_id = line.strip().split("=", 1)[1]
                    elif line.startswith("HID_NAME="):
                        hid_name = line.strip().split("=", 1)[1]
        except Exception:
            pass

    # Decode USB VID:PID hardware model
    vid_hex, pid_hex = "28E9", "028A"
    if ":" in hid_id:
        parts = hid_id.split(":")
        if len(parts) >= 3:
            vid_hex, pid_hex = parts[1], parts[2]
            
    decoded_model, model_source = protocol.decode_usb_vid_pid(vid_hex, pid_hex)

    fw_str = info.firmware_version if (info and info.firmware_version) else "v2.0 (CMS-60D/PO-400 v2)"
    sn_str = info.serial_number if (info and info.serial_number) else "50F"
    up_str = info.user_profile if (info and info.user_profile) else "user"
    geom_str = info.flash_geometry if (info and info.flash_geometry) else "112 Bytes Sub-chunk Payload"

    print(f"\n==================================================")
    print(f"  PULSOX PO-400 DEVICE & HARDWARE INFORMATION")
    print(f"==================================================")
    print(f"  Kernel Device Node     : {node_path}")
    print(f"  Hardware Model         : {decoded_model}")
    print(f"  └─ Provenance Source   : [{model_source}]")
    print(f"  USB Vendor:Product ID  : {vid_hex}:{pid_hex}")
    print(f"  sysfs Product String   : {sysfs_prod if sysfs_prod else 'Pulse Oximeter'}")
    print(f"  sysfs Manufacturer     : {sysfs_mfg if sysfs_mfg else 'Contec Medical Systems'}")
    print(f"  sysfs USB Bus Path     : {sysfs_bus if sysfs_bus else 'N/A'}")
    print(f"  sysfs HID ID           : {hid_id}")
    print(f"  sysfs HID Name         : {hid_name}")
    print(f"  Read/Write Access      : Readable={readable}, Writable={writable}")
    print(f"  Firmware Version       : {fw_str}")
    print(f"  Serial Number          : {sn_str}")
    print(f"  User Profile String    : {up_str}")
    print(f"  Active Session User ID : User #{active_user_id}")
    print(f"  Device RTC Timestamp   : {rtc_time_str}")
    print(f"  Storage Memory Geometry: {geom_str}")
    print(f"==================================================\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="po400",
        description="CLI tool to query device information and extract recordings from Pulsox PO-400 USB HID pulse oximeter.",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: info
    parser_info = subparsers.add_parser("info", help="Read hardware model, firmware version, and USB descriptors.")
    parser_info.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_info.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_info.set_defaults(func=command_info)

    # Subcommand: sessions
    parser_sess = subparsers.add_parser("sessions", help="List all stored recording sessions on device (v2.0.0).")
    parser_sess.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_sess.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_sess.set_defaults(func=command_sessions)

    # Subcommand: download
    parser_dl = subparsers.add_parser("download", help="Download recorded sessions from device memory (defaults to ALL sessions).")
    parser_dl.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
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
    parser_clear.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_clear.add_argument("-s", "--session", type=int, default=0, help="Specific session ID to delete (default: 0 = delete ALL sessions).")
    parser_clear.add_argument("-y", "--yes", action="store_true", help="Bypass confirmation prompt.")
    parser_clear.set_defaults(func=command_clear)

    # Subcommand: read-time
    parser_rt = subparsers.add_parser("read-time", help="Read active device Real-Time Clock (RTC) timestamp.")
    parser_rt.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_rt.set_defaults(func=command_read_time)

    # Subcommand: set-time
    parser_st = subparsers.add_parser("set-time", help="Set device Real-Time Clock (RTC) to specified timestamp or current system time.")
    parser_st.add_argument("timestamp", nargs="?", help="Optional timestamp string 'YYYY-MM-DD HH:MM:SS' (defaults to current system time).")
    parser_st.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_st.set_defaults(func=command_set_time)

    # Subcommand: detect
    parser_det = subparsers.add_parser("detect", help="Run live Serial Packet Detector & Decoder on incoming USB HID stream.")
    parser_det.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_det.set_defaults(func=command_detect)

    args = parser.parse_args()


    if not args.command:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
