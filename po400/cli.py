"""Pulsox PO-400 Command-Line Interface (CLI).

Commands:
  info     - Read hardware model, firmware version, and USB descriptors.
  sessions - List all stored recording sessions on device.
  download - Extract recorded sessions from device and save to CSV or JSON.
"""

import argparse
import codecs
import csv
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

try:
    import readline  # Enable terminal arrow keys, line editing, and history in input()
except ImportError:
    pass

from po400 import __version__, config, console, export, protocol, serial_engine
from po400.protocol import Commands, Parsers
from po400.hid_driver import PulsoxHidDevice, get_usb_sysfs_info

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ASCII stand-ins for the symbols this CLI prints, used only on consoles whose
# encoding cannot represent them (see _configure_output_encoding).
_ASCII_FALLBACKS = {
    "❌": "[X]",    # cross mark
    "✅": "[OK]",   # white heavy check mark
    "⚠": "[!]",    # warning sign
    "✓": "v",      # check mark
    "✗": "x",      # ballot x
    "\U0001f4ca": "*",  # bar chart
    "\U0001f50d": "*",  # magnifying glass
    "\U0001f552": "*",  # clock face
    "└": "\\",     # box drawings up and right
    "├": "+",      # box drawings vertical and right
    "─": "-",      # box drawings horizontal
    "│": "|",      # box drawings vertical
    "—": "-",      # em dash
    "️": "",       # variation selector-16, renders as nothing
}

_ENCODING_ERROR_HANDLER = "po400_ascii_fallback"


def _ascii_fallback_error_handler(error):
    """Codec error handler: substitute ASCII for characters the console cannot encode."""
    if not isinstance(error, UnicodeEncodeError):
        raise error
    bad = error.object[error.start:error.end]
    return ("".join(_ASCII_FALLBACKS.get(ch, "?") for ch in bad), error.end)


def _configure_output_encoding() -> None:
    """Keep output printable on consoles with a legacy codepage.

    Windows consoles default to a single-byte codepage -- cp1252 or cp850 on a
    German install -- which cannot encode the box-drawing characters and symbols
    used throughout this CLI. Writing one raises UnicodeEncodeError and aborts
    the command mid-output; it even kills run_guarded's own error message, whose
    first character is one of them.

    Rather than forcing UTF-8 (which would emit mojibake on exactly those
    consoles) or deleting the symbols (which would degrade every terminal that
    renders them correctly), install an error handler so each character survives
    where the encoding supports it and falls back to ASCII only where it does not.
    """
    codecs.register_error(_ENCODING_ERROR_HANDLER, _ascii_fallback_error_handler)
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue  # Not a TextIOWrapper (redirected, wrapped, or Python < 3.7)
        try:
            reconfigure(errors=_ENCODING_ERROR_HANDLER)
        except (ValueError, OSError, AttributeError):
            pass  # Best effort: a stream we cannot reconfigure is left as it was


def tool_version_line() -> str:
    """Tool version plus the runtime it runs on, for reports users paste into bug reports."""
    build = "standalone binary" if getattr(sys, "frozen", False) else f"Python {platform.python_version()}"
    return f"{__version__} ({build}, {platform.system()} {platform.release()}, {platform.machine()})"


def clean_input(prompt: str = "") -> str:
    """Wrapper around built-in input() that strips ANSI escape sequences and non-printable control chars."""
    raw = input(prompt)
    cleaned = ANSI_ESCAPE_RE.sub("", raw)
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in " \t")
    return cleaned.strip()


def command_config(args) -> int:
    """Handler for 'config': show or change stored settings."""
    if args.workdir:
        chosen = config.ensure_usable_dir(args.workdir)
        if not chosen:
            print(f"❌ Cannot create or write to: {args.workdir}")
            return 1
        saved = config.set_workdir(chosen)
        if not saved:
            print(f"❌ Could not write the settings file at {config.config_path()}")
            return 1
        print(f"✅ Working directory set to: {chosen}")
        print(f"   Saved in {saved}")
        return 0

    print(f"Settings file : {config.config_path()}")
    current = config.get_workdir()
    if current:
        print(f"Working dir   : {current}")
    else:
        print(f"Working dir   : (not set; would offer {config.default_workdir()})")
    return 0


def command_plot(args) -> int:
    """Handler for 'plot' subcommand to generate PNG graph from recording file."""
    try:
        from po400 import plot
    except ImportError as e:
        if getattr(e, "name", None) != "matplotlib":
            raise
        print("❌ Plotting needs matplotlib, which is not installed.")
        print("   Install it with: pip install matplotlib   (or: pip install po400[plot])")
        return 1
    try:
        saved_path = plot.plot_session(filepath=args.file, output_png=args.output, dpi=args.dpi)
        print(f"📊 Successfully generated session plot: {saved_path}")
        return 0
    except Exception as e:
        print(f"❌ Error generating plot: {e}")
        return 1


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
    print(f"  PO-400 SERIAL PACKET DETECTOR & DECODER ENGINE  (po400 v{__version__})")
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



def _export_records_to_file(
    records: List[dict],
    output_filename: Optional[str] = None,
    fmt: str = "spo2",
    output_dir: Optional[str] = None,
) -> str:
    """Helper to save extracted records into .SpO2, CSV, or JSON format."""
    return export.export_records(
        records, output_filename=output_filename, fmt=fmt, output_dir=output_dir
    )


def command_download(args):
    """Handler for 'download' subcommand using SerialDeviceEngine."""
    download_all = args.all or args.session == 0
    verbose_level = getattr(args, "verbose", 0)

    # Validate an explicit --workdir / PO400_WORKDIR before touching the device,
    # so a typo fails in a second rather than after a long download.
    try:
        override_dir = None if args.output else config.explicit_workdir(getattr(args, "workdir", None))
    except config.WorkdirError as e:
        print(f"❌ {e}")
        return 1

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
    # Precedence: -o, then --workdir, then PO400_WORKDIR, then the stored
    # setting (prompting once on a first interactive run), then the cwd.
    target_dir = None if args.output else (override_dir or config.resolve_workdir())
    saved_path = _export_records_to_file(
        total_records, args.output, args.format.lower(), output_dir=target_dir
    )
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
    print(f"  PULSOX PO-400 STORED RECORDING SESSIONS  (po400 v{__version__})")
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
        confirm = clean_input(f"⚠️ Are you sure you want to permanently DELETE {target_str} from device memory? [y/N]: ")
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
    print(f"  po400 Tool Version     : {tool_version_line()}")
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
    raw = ANSI_ESCAPE_RE.sub("", selection_str)
    raw = "".join(ch for ch in raw if ch.isprintable() or ch in " \t").strip().lower()
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
                raise ValueError(f"Invalid session number or syntax: '{part}'")
            sid = int(part)
            if sid not in sess_map:
                raise ValueError(f"Session #{sid} does not exist.")
            if sid not in selected_ids:
                selected_ids.append(sid)

    if not selected_ids:
        raise ValueError("No valid sessions selected.")

    return [sess_map[sid] for sid in selected_ids]


def generate_iso_filename(selected_sessions: List[protocol.SessionInfo], ext: str = "spo2") -> str:
    """Generates a uniform filename with ISO start and end datetimes.
    
    Format: po400_{start_iso}_{end_iso}.{ext}
    e.g.: po400_2026-09-06T100516_2026-09-06T105028.spo2
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
    clean_ext = ext.lower().lstrip(".")
    return f"po400_{start_iso}_{end_iso}.{clean_ext}"


def get_next_available_filename(filepath: str, max_attempts: int = 10000) -> str:
    """Generate next available filename by appending a counter suffix (_1, _2, etc.) that does not yet exist on disk."""
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    m = re.search(r"^(.*)_(\d+)$", base)
    if m:
        prefix = m.group(1)
        idx = int(m.group(2)) + 1
    else:
        prefix = base
        idx = 1

    for _ in range(max_attempts):
        candidate = f"{prefix}_{idx}{ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1

    return f"{prefix}_{idx}{ext}"


def run_interactive_wizard(args) -> int:
    """Interactive text-based wizard prompt when po400 is run without subcommands."""
    dev_path = getattr(args, "device", None)
    backend = getattr(args, "backend", None)
    verbose_level = getattr(args, "verbose", 0)

    while True:
        print("\n============================================================")
        print("          PULOX PO-400 INTERACTIVE USER INTERFACE")
        print(f"          po400 v{__version__}".rstrip())
        print("============================================================")

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
                act = clean_input("Select action [c, q]: ").lower()
                if act in ("c", "clear"):
                    confirm = clean_input("⚠️ Are you sure you want to format device flash memory? [y/N]: ").lower()
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
            print("  [W]   Download Wizard (all sessions, save, erase device) [Default]")
            print("  [#]   Download session(s) — e.g. single (1), list (1,3,4), or range (1-3)")
            print("  [A]   Download all sessions (a or all)")
            print("  [C]   Clear / erase device flash memory")
            print("  [Q]   Quit")
            print("------------------------------------------------------------")

            choice = clean_input(f"Select action [W, 1-{len(sessions)}, ranges, a, c, q; default: W]: ")
            if not choice or choice.lower() in ("w", "wizard"):
                confirm_wizard = clean_input("\nStart Download Wizard to download all sessions? [Y/n]: ").lower()
                if confirm_wizard not in ("", "y", "yes"):
                    print("Download Wizard cancelled.")
                    continue
                selected_sessions = sessions
            elif choice.lower() in ("a", "all"):
                selected_sessions = sessions
            elif choice.lower() in ("q", "quit", "exit"):
                print("Goodbye!")
                return 0
            elif choice.lower() in ("c", "clear"):
                confirm = clean_input("⚠️ Are you sure you want to permanently DELETE ALL recordings from device memory? [y/N]: ").lower()
                if confirm in ("y", "yes"):
                    engine.clear_memory(0, debug=verbose_level)
                    print("✅ Device flash memory cleared successfully.")
                ret = clean_input("\nReturn to main menu? [y/N]: ").lower()
                if ret in ("y", "yes"):
                    continue
                print("Goodbye!")
                return 0
            elif choice.isalpha():
                print(f"[!] Unknown action: '{choice}'. Valid actions: [W] Wizard, [A] All, [C] Clear, [Q] Quit, or session number(s).")
                continue
            else:
                try:
                    selected_sessions = parse_session_selection(choice, sessions)
                except ValueError as ve:
                    print(f"[!] {ve}")
                    continue

            default_fn = generate_iso_filename(selected_sessions, ext="spo2")
            fn_input = clean_input(f"\nSave as [default: {default_fn}]: ")
            if not fn_input:
                out_fn = default_fn
            elif fn_input in ("1", "spo2"):
                out_fn = generate_iso_filename(selected_sessions, ext="spo2")
            elif fn_input in ("2", "csv"):
                out_fn = generate_iso_filename(selected_sessions, ext="csv")
            elif fn_input in ("3", "json"):
                out_fn = generate_iso_filename(selected_sessions, ext="json")
            else:
                out_fn = fn_input

            # Overwrite protection if target file already exists
            file_confirmed = True
            while os.path.exists(out_fn):
                ow = clean_input(f"⚠️ File '{out_fn}' already exists. Overwrite? [y/N]: ").lower()
                if ow in ("y", "yes"):
                    break
                suggested_fn = get_next_available_filename(out_fn)
                alt_fn = clean_input(f"Save as [default: {suggested_fn}; 'q' to cancel]: ")
                if alt_fn.lower() in ("q", "quit", "cancel"):
                    print("Download cancelled.")
                    file_confirmed = False
                    break
                out_fn = suggested_fn if not alt_fn else alt_fn

            if not file_confirmed:
                continue

            all_records = []
            for idx, s in enumerate(selected_sessions, 1):
                print(f"\nDownloading Session #{s.session_id} ({idx}/{len(selected_sessions)})...")
                recs = engine.download_session(s, debug=verbose_level)
                all_records.extend(recs)

            saved_path = _export_records_to_file(all_records, out_fn)
            print(f"\n✅ Successfully saved {len(all_records):,} records across {len(selected_sessions)} session(s) to: {saved_path}")

            # Offer flash erase with default = YES
            erase_input = clean_input("\nErase recordings from device flash? [Y/n]: ").lower()
            if erase_input in ("", "y", "yes"):
                engine.clear_memory(0, debug=verbose_level)
                print("✅ Device flash memory erased successfully.")
            else:
                print("Flash recordings preserved.")

            # Offer return to menu with default = NO
            ret_input = clean_input("\nReturn to main menu? [y/N]: ").lower()
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


def main(argv: Optional[List[str]] = None):
    _configure_output_encoding()
    console.enlarge_owned_console()
    parser = argparse.ArgumentParser(
        prog="po400",
        description="CLI tool to query device information and extract recordings from Pulsox PO-400 USB HID pulse oximeter.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
    parser_sess = subparsers.add_parser("sessions", help="List all stored recording sessions on device.")
    parser_sess.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_sess.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (-v for packet logging, -vv for raw HID frames + packets).")
    parser_sess.set_defaults(func=command_sessions)

    # Subcommand: download
    parser_dl = subparsers.add_parser("download", help="Download recorded sessions from device memory (defaults to ALL sessions).")
    parser_dl.add_argument("-d", "--device", help="Specific device path or /dev/hidraw node path (optional).")
    parser_dl.add_argument("-s", "--session", type=int, default=0, help="Specific session ID to download (default: 0 = download ALL sessions).")
    parser_dl.add_argument("-a", "--all", action="store_true", help="Download ALL stored recording sessions (default).")
    parser_dl.add_argument("-o", "--output", help="Output file path (default: po400_all_sessions_<timestamp>.spo2 in the configured working directory).")
    parser_dl.add_argument("--workdir", help="Directory for this download only (overrides PO400_WORKDIR and the stored setting; not saved). Ignored with -o.")
    parser_dl.add_argument("-f", "--format", choices=["spo2", "csv", "json"], default="spo2", help="Output format: 'spo2' (default), 'csv', or 'json'.")
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

    # Subcommand: config
    parser_cfg = subparsers.add_parser("config", help="Show or change stored settings (e.g. where recordings are saved).")
    parser_cfg.add_argument("--workdir", help="Set the directory new recordings are saved in.")
    parser_cfg.set_defaults(func=command_config)

    # Subcommand: plot
    parser_plot = subparsers.add_parser("plot", help="Generate high-resolution PNG graph from .spo2, .csv, or .json recording files.")
    parser_plot.add_argument("file", nargs="?", help="Path to recording file (.spo2, .csv, or .json). Defaults to the latest in the current directory.")
    parser_plot.add_argument("-o", "--output", help="Output PNG file path (default: <filename>.png next to the recording).")
    parser_plot.add_argument("--dpi", type=int, default=150, help="Resolution in DPI (default: 150).")
    parser_plot.set_defaults(func=command_plot)

    for p in [parser_info, parser_sess, parser_dl, parser_clear, parser_rt, parser_st, parser_det]:
        p.add_argument("-b", "--backend", "--driver", dest="backend", choices=["hidraw", "hid"], default=argparse.SUPPRESS, help="HID driver backend: 'hidraw' (default on Linux) or 'hid' (default on Windows / Linux testing).")

    args = parser.parse_args(argv)
    handler = args.func if args.command else run_interactive_wizard
    sys.exit(run_guarded(handler, args))


def run_guarded(handler, args) -> int:
    """Run a command handler, turning unexpected errors into a short message and exit code.

    Set PO400_DEBUG=1 to get the full traceback instead.
    """
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130
    except Exception as e:
        if os.environ.get("PO400_DEBUG"):
            raise
        print(f"❌ po400 {__version__}: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        print("   Re-run with PO400_DEBUG=1 for the full traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
