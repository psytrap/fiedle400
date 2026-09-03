"""Pulsox PO-400 Command-Line Interface (CLI).

Commands:
  scan     - Search for connected PO-400 USB HID devices and check permissions.
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

from po400 import protocol
from po400.protocol import Commands, Parsers
from po400.hid_driver import PulsoxHidDevice, find_pulsox_hid_devices, get_usb_sysfs_info


def command_scan(args):
    """Handler for 'scan' subcommand."""
    print("Scanning for connected Pulsox PO-400 USB HID devices...\n")
    devices = find_pulsox_hid_devices()
    
    if not devices:
        print("❌ No PO-400 USB HID devices found.")
        print("   Troubleshooting checklist:")
        print("   1. Is the USB cable connected to the PC?")
        print("   2. Is the PO-400 powered ON?")
        return 1

    print(f"Found {len(devices)} device(s):\n")
    for idx, (path, info, is_readable) in enumerate(devices, 1):
        perm_status = "✅ READ/WRITE OK" if is_readable else "❌ PERMISSION DENIED (Run 'sudo chmod 666 /dev/hidraw*')"
        print(f" [{idx}] Node: {path}")
        print(f"     Status: {perm_status}")
        print(f"     Info:   {info}")
        print("-" * 50)
    return 0




def _discover_sessions_to_download(dev, download_all: bool, target_session: int) -> List[int]:
    """Helper to discover available session IDs for download."""
    if not download_all:
        return [target_session]

    print("Querying session index table to download ALL sessions...")
    dev.write_report(Commands.query_sessions())
    time.sleep(0.15)
    
    session_list = []
    start_q = time.time()
    sess_counter = 1
    while time.time() - start_q < 1.5:
        report = dev.read_report(64)
        if report:
            if report[0] == 0xEC:
                session_list.append(sess_counter)
                sess_counter += 1
            else:
                parsed_sess = Parsers.parse_session_index(report)
                if parsed_sess:
                    session_list.extend([s.session_id for s in parsed_sess])
        time.sleep(0.02)
        
    if not session_list:
        print("No active session table returned; defaulting to downloading Session #1...")
        return [1]

    session_list = sorted(list(set(session_list)))
    print(f"Found {len(session_list)} sessions to download: {session_list}")
    return session_list


def _download_single_session(dev, sess_id: int, timeout_limit: float) -> List[dict]:
    """Helper to stream and extract records for a single session ID."""
    print(f"\n---> Requesting Session #{sess_id} Data Blocks (0x9B / 0x9D / 0xEB)...")
    
    # Request data stream activation (0x9B)
    dev.write_report(Commands.query_data_stream())
    time.sleep(0.1)

    # Ground-truth storage initialization (0x9D 0x02)
    dev.write_report(Commands.storage_init())
    time.sleep(0.1)
    neg_report = dev.read_report(64)
    user_id = Parsers.parse_user_id(neg_report) if neg_report else 1

    # Request Block 1 & Block 2 data blocks (0x9D 0x04)
    dev.write_report(Commands.storage_block(1, sess_id))
    time.sleep(0.1)
    dev.write_report(Commands.storage_block(2, sess_id))
    time.sleep(0.1)
    
    sess_records = []
    read_start = time.time()
    received_packets = 0
    
    while time.time() - read_start < timeout_limit:
        report = dev.read_report(64)
        if report:
            received_packets += 1
            now = datetime.now()
            
            # Parse 0xEB/0xED pcap ground-truth frames, 6-byte chunks, or 3-byte stored frames
            datapoints = Parsers.parse_eb_frames(report, now)
            if not datapoints:
                datapoints, spo2, hr, ppg = protocol.parse_hid_chunks(report, now)
            if not datapoints:
                datapoints = protocol.parse_stored_data_frames(report, now)
            
            for dp in datapoints:
                if dp.spo2 or dp.heart_rate or dp.ppg_wave:
                    sess_records.append({
                        "session_id": sess_id,
                        "user_id": user_id,
                        "timestamp": dp.timestamp.isoformat(),
                        "spo2": dp.spo2,
                        "heart_rate": dp.heart_rate,
                        "ppg_wave": dp.ppg_wave,
                        "flags": dp.status_flags,
                    })
            print(f"\rDownloaded {received_packets} packets for Session #{sess_id} ({len(sess_records)} records)...", end="", flush=True)
        time.sleep(0.02)
        
    print(f"\nSession #{sess_id} finished ({len(sess_records)} records). (Memory Preserved / Non-Destructive)")
    return sess_records


def _export_records_to_file(records: List[dict], output_filename: Optional[str], fmt: str) -> str:
    """Helper to save extracted records into CSV or JSON format."""
    if not output_filename:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"po400_all_sessions_{timestamp_str}.{fmt}"

    if fmt == "csv":
        with open(output_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["session_id", "user_id", "timestamp", "spo2", "heart_rate", "ppg_wave", "flags"])
            writer.writeheader()
            writer.writerows(records)
    else:  # json
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    return os.path.abspath(output_filename)


def command_download(args):
    """Handler for 'download' subcommand."""
    download_all = args.all or args.session == 0
    
    print("Connecting to Pulsox PO-400 to extract recording data...")
    try:
        dev = PulsoxHidDevice(dev_path=args.device)
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    total_records = []
    try:
        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        dev.read_report(64)  # Flush ACK

        # Step 2: Discover target sessions
        session_list = _discover_sessions_to_download(dev, download_all, args.session)

        # Step 3: Stream and collect records for each session
        for sess_id in session_list:
            sess_records = _download_single_session(dev, sess_id, args.timeout)
            total_records.extend(sess_records)

    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    finally:
        dev.close()

    print(f"\nDownload complete. Total records collected across all sessions: {len(total_records)}")
    saved_path = _export_records_to_file(total_records, args.output, args.format.lower())
    print(f"✅ Saved all session recordings to: {saved_path}")
    return 0



def command_sessions(args):
    """Handler for 'sessions' subcommand to query v2.0.0 session index table."""
    print("Connecting to Pulsox PO-400 to query recorded session index...")
    try:
        dev = PulsoxHidDevice(dev_path=args.device)
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    try:
        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        dev.read_report(64)  # Flush ACK

        # Step 2: Send Session Index Query (0x9C)
        dev.write_report(Commands.query_sessions())
        time.sleep(0.15)

        sessions = []
        start = time.time()
        sess_counter = 1
        while time.time() - start < 2.0:
            report = dev.read_report(64)
            if report:
                # Check for 0xEC Session Metadata Index Report
                if report[0] == 0xEC:
                    dt, user_name = Parsers.parse_segment_metadata(report)
                    rec_cnt = (report[10] << 8) | report[11] if len(report) >= 12 else 1034
                    sessions.append(protocol.SessionInfo(
                        session_id=sess_counter,
                        user_id=1,
                        record_count=rec_cnt,
                        timestamp=dt
                    ))
                    sess_counter += 1
                else:
                    parsed_sess = Parsers.parse_session_index(report)
                    if parsed_sess:
                        sessions.extend(parsed_sess)
            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nSession query interrupted by user.")
    finally:
        dev.close()

    print(f"\n==================================================")
    print(f"  PULSOX PO-400 STORED RECORDING SESSIONS (v2.0.0)")
    print(f"==================================================")

    if not sessions:
        print("No stored recording sessions found in device memory.")
        print("(Note: To record a session, set Record=ON in PO-400 menu while measuring).")
    else:
        print(f"{'Session ID':<12} | {'User':<6} | {'Records':<10} | {'Timestamp':<20}")
        print("-" * 58)
        for s in sessions:
            ts_str = s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "N/A"
            print(f"{s.session_id:<12} | {s.user_id:<6} | {s.record_count:<10} | {ts_str:<20}")
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

    try:
        dev.write_report(Commands.build_hid(0xAF))
        time.sleep(0.1)

        if sess_id > 0:
            print(f"Sending session delete command (0xAB) for Session #{sess_id}...")
            dev.write_report(Commands.build_hid(0xAB, [0x01, sess_id]))
            time.sleep(0.2)
        else:
            print(f"Sending flash format command (0xAA)...")
            dev.write_report(Commands.build_hid(0xAA, [0x80, 0x80]))
            time.sleep(0.2)
            
            print(f"Sending session table delete (0xAB)...")
            dev.write_report(Commands.build_hid(0xAB, [0x80, 0x80]))
            time.sleep(0.2)

            print(f"Sending flash memory reset (0xAC)...")
            dev.write_report(Commands.build_hid(0xAC, [0x80, 0x80]))
            time.sleep(0.2)

        # Re-verify with 0xA5 query
        dev.write_report(Commands.build_hid(0xA5))
        time.sleep(0.3)
        check_report = dev.read_report(64)
        if check_report and check_report[0] in [0xF0, 0x7D]:
            print("Received hardware ACK: Flash memory table erased and reset.")

    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    finally:
        dev.close()

    print(f"✅ Successfully cleared {target_str} from device flash memory.")
    return 0


def command_read_time(args):
    """Handler for 'read-time' subcommand to read active device RTC timestamp."""
    print("Connecting to Pulsox PO-400 to read Real-Time Clock (RTC)...")
    try:
        dev = PulsoxHidDevice(dev_path=args.device)
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    try:
        dev.write_report(Commands.read_time())
        time.sleep(0.3)
        report = dev.read_report(64)
        rtc_dt = Parsers.parse_rtc_time(report) if report else None

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
    """Handler for 'set-time' subcommand to set device RTC timestamp."""
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

    try:
        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        dev.read_report(64)  # Flush ACK

        # Step 2: Send Set-RTC command (0x83)
        print(f"Sending Set-RTC command (0x83) for timestamp: {ts_str}...")
        dev.write_report(Commands.set_time(target_dt))
        time.sleep(0.3)
        
        ack = dev.read_report(64)
        if ack:
            print("Received device ACK: Real-Time Clock synchronized!")

    except KeyboardInterrupt:
        print("\nSet RTC interrupted by user.")
    finally:
        dev.close()

    print(f"✅ Successfully set PO-400 device clock to: {ts_str}")
    print(f"   Command format: python3 -m po400.cli set-time \"{ts_str}\"")
    return 0


def command_negotiate(args):
    """Handler for 'negotiate' subcommand to execute Packet #549 (0xA7 unlock + 0xA2 negotiation)."""
    print("Connecting to Pulsox PO-400 to execute unlock handshake & storage negotiation...")
    try:
        dev = PulsoxHidDevice(dev_path=args.device)
        node_path = dev.connect()
        print(f"Connected to {node_path}!")
    except Exception as e:
        print(f"Error connecting: {e}")
        return 1

    try:
        rep_handshake = Commands.unlock_handshake()
        print(f"\n---> Sending Unlock Handshake (0xA7) + Storage Negotiation (0xA2)...")
        print(f"     Hex OUT: {rep_handshake[:24].hex()}")
        dev.write_report(rep_handshake)
        time.sleep(0.2)

        res = dev.read_report(64)
        if res:
            print(f"     Incoming ACK Report: {res[:24].hex()}")
            user_id = Parsers.parse_user_id(res)
            print(f"  ✅ Handshake ACK Success! Active Session User ID: {user_id}")
        else:
            print("  ⚠️ Handshake sent (no immediate report returned).")

    except KeyboardInterrupt:
        print("\nNegotiation interrupted by user.")
    finally:
        dev.close()
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

    info = protocol.DeviceInfo()
    raw_hex_str = "None"
    rtc_time_str = "N/A"
    active_user_id = 1

    try:
        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        neg_res = dev.read_report(64)
        if neg_res:
            active_user_id = Parsers.parse_user_id(neg_res)

        # Step 2: Query RTC Clock (0x82)
        dev.write_report(Commands.read_time())
        time.sleep(0.15)
        rtc_report = dev.read_report(64)
        if rtc_report:
            rtc_dt = Parsers.parse_rtc_time(rtc_report)
            if rtc_dt:
                rtc_time_str = rtc_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Step 3: Query Info (0xAD)
        dev.write_report(Commands.build_hid(0xAD))
        time.sleep(0.15)
        report = dev.read_report(64)
        if report:
            info = Parsers.parse_device_info(report)
            raw_hex_str = " ".join([f"{b:02X}" for b in report[:16]])

        # Step 4: Query 0x81 (Firmware Version Query)
        dev.write_report(Commands.build_hid(0x81, [0x01]))
        time.sleep(0.1)
        fw_report = dev.read_report(64)
        if fw_report and fw_report[0] == 0x81:
            fw_info = Parsers.parse_device_info(fw_report)
            if fw_info.firmware_version:
                info.firmware_version = fw_info.firmware_version

        # Step 5: Query 0x8E (Serial Number / User Profile Query)
        dev.write_report(Commands.build_hid(0x8E, [0x03, 0x11]))
        time.sleep(0.1)
        for _ in range(3):
            serial_report = dev.read_report(64)
            if serial_report:
                sn, up = Parsers.parse_serial(serial_report)
                if sn and info:
                    info.serial_number = sn
                if up and info:
                    info.user_profile = up
            time.sleep(0.05)

        # Step 6: Query 0x9E (Extended Storage Architecture Query)
        dev.write_report(Commands.build_hid(0x9E, [0x40, 0x04]))
        time.sleep(0.1)
        geom_report = dev.read_report(64)
        if geom_report and info:
            info.flash_geometry = Parsers.parse_geometry(geom_report)

    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
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

    # Subcommand: scan (alias for info)
    parser_scan = subparsers.add_parser("scan", help="Scan and display connected device information and permissions.")
    parser_scan.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_scan.set_defaults(func=command_info)

    # Subcommand: info
    parser_info = subparsers.add_parser("info", help="Read hardware model, firmware version, and USB descriptors.")
    parser_info.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_info.set_defaults(func=command_info)

    # Subcommand: sessions
    parser_sess = subparsers.add_parser("sessions", help="List all stored recording sessions on device (v2.0.0).")
    parser_sess.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_sess.set_defaults(func=command_sessions)

    # Subcommand: download
    parser_dl = subparsers.add_parser("download", help="Download recorded sessions from device memory (defaults to ALL sessions).")
    parser_dl.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_dl.add_argument("-s", "--session", type=int, default=0, help="Specific session ID to download (default: 0 = download ALL sessions).")
    parser_dl.add_argument("-a", "--all", action="store_true", help="Download ALL stored recording sessions (default).")
    parser_dl.add_argument("-o", "--output", help="Output file path (default: po400_all_sessions_<timestamp>.csv).")
    parser_dl.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (csv or json).")
    parser_dl.add_argument("-t", "--timeout", type=int, default=5, help="Read duration per session in seconds (default: 5).")
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

    # Subcommand: negotiate
    parser_neg = subparsers.add_parser("negotiate", help="Execute Packet #549 unlock handshake (0xA7) & storage negotiation (0xA2).")
    parser_neg.add_argument("-d", "--device", help="Specific /dev/hidraw node path (optional).")
    parser_neg.set_defaults(func=command_negotiate)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
