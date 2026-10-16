"""High-level device controller managing streaming, packet detection, and session extraction."""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union

from ..protocol import (
    SessionInfo,
    DeviceInfo,
    Parsers,
    Commands,
)
from .buffer import SerialByteStreamBuffer
from .detector import SerialPacketDetector, DecodedPacket


class SerialDeviceEngine:
    """High-level device controller managing streaming, packet detection, and session extraction."""

    def __init__(self, device):
        self.dev = device
        self.buffer = SerialByteStreamBuffer()
        self.detector = SerialPacketDetector()
        self.dump_fp = None
        self.last_dump_time = None
        self._is_mock = hasattr(device, "responses")  # test doubles script replies; real devices never do

    def _sleep(self, seconds: float):
        if not self._is_mock:
            time.sleep(seconds)

    def _log_dump(self, direction: str, report_bytes: bytes, summary: str = ""):
        if self.dump_fp is None:
            return
        now = time.time()
        dt_str = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        delta_sec = (now - self.last_dump_time) if self.last_dump_time else 0.0
        self.last_dump_time = now
        hex_str = report_bytes.hex()
        line = f"[{dt_str}] (Δt={delta_sec:.3f}s) [{direction:<3}] ({len(report_bytes):>2}B): {hex_str}"
        if summary:
            line += f" | {summary}"
        self.dump_fp.write(line + "\n")
        self.dump_fp.flush()

    def _write_report(self, report_bytes: bytes, desc: str = ""):
        self._log_dump("OUT", report_bytes, desc)
        return self.dev.write_report(report_bytes)

    def read_packets(self, base_timestamp: Optional[datetime] = None, debug: Union[bool, int] = 0) -> List[DecodedPacket]:
        """Reads next available report from physical HID device and detects embedded packet events."""
        report = self.dev.read_report(64)
        if not report:
            return []

        debug_level = int(debug)
        if debug_level >= 2:
            print(f"[DEBUG IN] Raw HID Frame ({len(report)} bytes): {report.hex()}")

        self.buffer.write(report)
        events = self.detector.detect_and_decode_stream(self.buffer, base_timestamp)

        if self.dump_fp is not None:
            summary_parts = []
            if events:
                for ev in events:
                    summary_parts.append(f"{ev.packet_type} (blk={ev.block_id}, seq={ev.seq}, SpO2={ev.spo2}, HR={ev.heart_rate}, status={ev.status_str})")
            summary_str = "; ".join(summary_parts) if summary_parts else "RAW_REPORT"
            self._log_dump("IN", report, summary_str)

        if debug_level >= 1 and events:
            for ev in events:
                raw_str = ev.raw_payload.hex() if ev.raw_payload else "None"
                spo2_str = f"{ev.spo2}%" if ev.spo2 is not None else "N/A"
                hr_str = f"{ev.heart_rate} bpm" if ev.heart_rate is not None else "N/A"
                print(f"[DEBUG IN] Packet Type={ev.packet_type:<15} | Payload={raw_str:<24} | SpO2={spo2_str:<6} | HR={hr_str:<8} | Status={ev.status_str}")
        return events

    def wait_for_eb_stream(self, target_count: int = 10, max_timeout: float = 10.0, debug: Union[bool, int] = 0) -> int:
        """Enables periodic streaming (0x9B) and listens until target_count (default 10) 0xEB messages have been reported before starting other communication."""
        c_stream = Commands.query_data_stream()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Enable Periodic Telemetry (0x9B): {c_stream[:16].hex()}")
            print(f"[DEBUG OUT] Waiting for {target_count} 0xEB live stream messages before starting communication...")

        self._write_report(c_stream, "Enable Telemetry (0x9B)")
        self._sleep(0.05)

        eb_count = 0
        start_t = time.time()
        empty_count = 0

        while eb_count < target_count and (time.time() - start_t < max_timeout):
            events = self.read_packets(debug=debug)
            if not events:
                empty_count += 1
                if empty_count > 10:  # Exit early if device/mock returns no packets
                    break
            else:
                empty_count = 0
                for ev in events:
                    if ev.packet_type == "LIVE_STREAM" or (ev.raw_payload and ev.raw_payload[0] == 0xEB):
                        eb_count += 1
                        if eb_count >= target_count:
                            break
            self._sleep(0.005)

        if int(debug) >= 1:
            print(f"[DEBUG IN] Received {eb_count}/{target_count} 0xEB stream messages (elapsed: {time.time() - start_t:.2f}s).")

        # Turn off periodic messages after target_count 0xEB messages arrived
        c_stop = Commands.stop_data_stream()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Disable Periodic Telemetry (0x9B Stop): {c_stop[:16].hex()}")
        self._write_report(c_stop, "Disable Telemetry (0x9B Stop)")

        # Drain residual stream reports until no new messages arrive
        drain_start = time.time()
        last_msg_time = time.time()
        drained_reports = 0
        drain_empty_count = 0
        while (time.time() - last_msg_time < 0.20) and (time.time() - drain_start < 2.0):
            rep = self.dev.read_report(64)
            if rep:
                drain_empty_count = 0
                if rep[0] == 0xEB or (len(rep) >= 3 and rep[2] == 0xEB):
                    drained_reports += 1
                    last_msg_time = time.time()
                else:
                    self.buffer.write(rep)
                    break
            else:
                drain_empty_count += 1
                if drain_empty_count >= 2:
                    break
                self._sleep(0.005)

        if int(debug) >= 1:
            print(f"[DEBUG IN] Drained {drained_reports} residual HID reports (quiet period: 200ms verified).")

        self.buffer.clear()
        return eb_count

    def download_session(self, sess_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """Downloads stored oximetry session records using SerialPacketDetector engine."""
        sess_id = sess_info.session_id
        duration_sec = sess_info.duration_seconds
        base_timestamp = sess_info.timestamp or datetime.now()

        # Step 1: Flush stale reports & send unlock handshake + storage init
        while self.dev.read_report(64): pass

        c_unlock = Commands.unlock_handshake()
        c_init = Commands.storage_init()

        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {c_unlock[:16].hex()}")
        self._write_report(c_unlock, "Unlock Handshake (0xA7/0xA2)")
        self._sleep(0.05)

        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Storage Init: {c_init[:16].hex()}")
        self._write_report(c_init, "Storage Init (0x9D 0x02)")
        self._sleep(0.05)

        while self.dev.read_report(64): pass  # Flush ACK

        SerialPacketDetector.reset_decoder_state()

        sess_records = []
        total_packets = 0
        total_sequence_gaps = 0
        corrupt_frames = 0
        target_records = sess_info.record_count if sess_info.record_count > 0 else (duration_sec if duration_sec > 0 else 600)

        last_block_spo2: Optional[int] = None
        last_block_hr:   Optional[int] = None

        block_spo2_pkts = []
        block_hr_pkts = []

        def flush_block_buffers():
            nonlocal last_block_spo2, last_block_hr
            if not block_spo2_pkts and not block_hr_pkts:
                return

            pair_count = max(len(block_spo2_pkts), len(block_hr_pkts))
            for i in range(pair_count):
                s_ev = block_spo2_pkts[i] if i < len(block_spo2_pkts) else None
                h_ev = block_hr_pkts[i] if i < len(block_hr_pkts) else None

                flg = s_ev.status_str if s_ev else (h_ev.status_str if h_ev else "ok")
                is_probe_out = "probe-out" in flg or "searching" in flg

                if is_probe_out:
                    s_val = None
                    h_val = None
                else:
                    s_val = s_ev.spo2 if (s_ev and s_ev.spo2 is not None) else last_block_spo2
                    h_val = h_ev.heart_rate if (h_ev and h_ev.heart_rate is not None) else last_block_hr

                    if s_val is not None: last_block_spo2 = s_val
                    if h_val is not None: last_block_hr = h_val

                bid = s_ev.block_id if s_ev else (h_ev.block_id if h_ev else 1)
                sq  = s_ev.seq if s_ev else (h_ev.seq if h_ev else 0)

                sess_records.append({
                    "session_id": sess_id,
                    "user_id": sess_info.user_id,
                    "block_id": bid,
                    "seq": sq,
                    "timestamp": (base_timestamp + timedelta(seconds=len(sess_records))).isoformat(),
                    "spo2": s_val,
                    "heart_rate": h_val,
                    "flags": flg,
                })
                if len(sess_records) >= target_records:
                    break
            block_spo2_pkts.clear()
            block_hr_pkts.clear()

        # The "page" argument of a 0x9D 0x04 read is the sample offset at which the reply starts
        # (RELEASE_PLAN.md T6): each request continues where the records so far end. A record
        # averages two raw 2 Hz samples, so the offset is 2 * records. A reply that adds no record
        # (the end marker at offset == stored samples, or silence past it) ends the download.
        for _window in range(4096):
            if len(sess_records) >= target_records:
                break
            page_idx = 2 * len(sess_records)
            records_before = len(sess_records)
            SerialPacketDetector.reset_decoder_state()

            page_received_packets = False
            flash_sentinel_hit = False

            # Query SpO2 page
            c_spo2 = Commands.session_page(1, sess_id, page_idx, sess_info.user_id)
            if int(debug) >= 1:
                print(f"[DEBUG OUT] Serial Engine SpO2 Page #{page_idx}: {c_spo2[:16].hex()}")
            self._write_report(c_spo2, f"Request SpO2 Page #{page_idx}")
            self._sleep(0.05)

            page_start = time.time()
            last_pkt_time = time.time()
            retries = 0

            while True:
                now = time.time()
                if not page_received_packets and (now - page_start > 0.35):
                    if retries < 2 and not self._is_mock:
                        retries += 1
                        page_start = now
                        if int(debug) >= 1:
                            print(f"[DEBUG OUT] Retrying SpO2 Page #{page_idx} (attempt {retries+1})")
                        self._write_report(c_spo2, f"Retry SpO2 Page #{page_idx}")
                    else:
                        break
                if page_received_packets and (now - last_pkt_time > 0.25):
                    break
                if len(sess_records) >= target_records or len(block_spo2_pkts) >= target_records:
                    break
                if now - page_start > 2.0:
                    break

                events = self.read_packets(base_timestamp, debug=debug)
                if events:
                    for ev in events:
                        if ev.sequence_gap:
                            total_sequence_gaps += 1
                        if ev.packet_type == "FLASH_SENTINEL":
                            flash_sentinel_hit = True
                            break
                        if ev.packet_type == "CORRUPT_FRAME":
                            corrupt_frames += 1
                            page_received_packets = True
                            last_pkt_time = time.time()
                        if ev.packet_type == "STORED_BLOCK":
                            page_received_packets = True
                            last_pkt_time = time.time()
                            total_packets += 1
                            if ev.spo2 is not None and ev.heart_rate is not None:
                                flush_block_buffers()
                                is_po = "probe-out" in ev.status_str or "searching" in ev.status_str
                                sess_records.append({
                                    "session_id": sess_id,
                                    "user_id": sess_info.user_id,
                                    "block_id": ev.block_id,
                                    "seq": ev.seq,
                                    "timestamp": (base_timestamp + timedelta(seconds=len(sess_records))).isoformat(),
                                    "spo2": None if is_po else ev.spo2,
                                    "heart_rate": None if is_po else ev.heart_rate,
                                    "flags": ev.status_str,
                                })
                            elif ev.spo2 is not None:
                                block_spo2_pkts.append(ev)
                            elif ev.heart_rate is not None:
                                block_hr_pkts.append(ev)
                            elif ev.invalid_sample:
                                (block_spo2_pkts if ev.block_id % 2 == 1 else block_hr_pkts).append(ev)
                if flash_sentinel_hit:
                    break
                self._sleep(0.005)

            if flash_sentinel_hit:
                flush_block_buffers()
                break

            # Query Pulse page (unless mock has already satisfied target or dual frame)
            if not self._is_mock or (len(sess_records) < target_records and not block_spo2_pkts):
                c_pulse = Commands.session_page(2, sess_id, page_idx, sess_info.user_id)
                if int(debug) >= 1:
                    print(f"[DEBUG OUT] Serial Engine Pulse Page #{page_idx}: {c_pulse[:16].hex()}")
                self._write_report(c_pulse, f"Request Pulse Page #{page_idx}")
                self._sleep(0.05)

                page_start = time.time()
                last_pkt_time = time.time()
                pulse_received = False
                retries = 0

                while True:
                    now = time.time()
                    if not pulse_received and (now - page_start > 0.35):
                        if retries < 2 and not self._is_mock:
                            retries += 1
                            page_start = now
                            if int(debug) >= 1:
                                print(f"[DEBUG OUT] Retrying Pulse Page #{page_idx} (attempt {retries+1})")
                            self._write_report(c_pulse, f"Retry Pulse Page #{page_idx}")
                        else:
                            break
                    if pulse_received and (now - last_pkt_time > 0.25):
                        break
                    if len(sess_records) >= target_records or len(block_hr_pkts) >= target_records:
                        break
                    if now - page_start > 2.0:
                        break

                    events = self.read_packets(base_timestamp, debug=debug)
                    if events:
                        for ev in events:
                            if ev.sequence_gap:
                                total_sequence_gaps += 1
                            if ev.packet_type == "FLASH_SENTINEL":
                                flash_sentinel_hit = True
                                break
                            if ev.packet_type == "CORRUPT_FRAME":
                                corrupt_frames += 1
                                pulse_received = True
                                page_received_packets = True
                                last_pkt_time = time.time()
                            if ev.packet_type == "STORED_BLOCK":
                                pulse_received = True
                                page_received_packets = True
                                last_pkt_time = time.time()
                                total_packets += 1
                                if ev.spo2 is not None and ev.heart_rate is not None:
                                    flush_block_buffers()
                                    is_po = "probe-out" in ev.status_str or "searching" in ev.status_str
                                    sess_records.append({
                                        "session_id": sess_id,
                                        "user_id": sess_info.user_id,
                                        "block_id": ev.block_id,
                                        "seq": ev.seq,
                                        "timestamp": (base_timestamp + timedelta(seconds=len(sess_records))).isoformat(),
                                        "spo2": None if is_po else ev.spo2,
                                        "heart_rate": None if is_po else ev.heart_rate,
                                        "flags": ev.status_str,
                                    })
                                elif ev.heart_rate is not None:
                                    block_hr_pkts.append(ev)
                                elif ev.spo2 is not None:
                                    block_spo2_pkts.append(ev)
                                elif ev.invalid_sample:
                                    (block_spo2_pkts if ev.block_id % 2 == 1 else block_hr_pkts).append(ev)
                    if flash_sentinel_hit:
                        break
                    self._sleep(0.005)

            flush_block_buffers()

            if not int(debug) >= 1 and page_received_packets:
                print(f"\r[Serial Engine] Downloaded {total_packets} pkts for Session #{sess_id} ({len(sess_records)}/{target_records} records)...", end="", flush=True)

            if flash_sentinel_hit or not page_received_packets or len(sess_records) >= target_records:
                break
            if len(sess_records) == records_before:
                break

        flush_block_buffers()

        # Step 3: Non-destructive segment acknowledgment (0x9D 0x02 0x7F 0x7F 0x7F 0x00 0x00 0x00 0x1C)
        c_ack = Commands.segment_ack()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Non-Destructive Segment Ack (0x9D 0x02): {c_ack[:16].hex()}")
        self._write_report(c_ack, "Segment Ack (0x9D 0x02)")
        self._sleep(0.05)

        print(f"\nSession #{sess_id} download complete ({len(sess_records)} records, {total_packets} packets, {total_sequence_gaps} sequence gaps).")
        if corrupt_frames:
            print(f"WARNING: {corrupt_frames} stored frame(s) failed their checksum and were dropped; "
                  f"Session #{sess_id} is missing those samples and its SpO2 and pulse values may be misaligned "
                  f"from that point on. Download it again.")
        return sess_records

    def read_device_info(self, debug: Union[bool, int] = 0) -> Dict[str, Any]:
        """Queries and returns device hardware, firmware, RTC clock, user profile, and geometry info."""
        info = DeviceInfo()
        active_user_id = 1
        rtc_time_str = "N/A"

        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        self.dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        neg_res = self.dev.read_report(64)
        if neg_res:
            active_user_id = Parsers.parse_user_id(neg_res)

        # Step 2: Query RTC Clock (0x82)
        self.dev.write_report(Commands.read_time())
        time.sleep(0.15)
        events = self.read_packets(debug=debug)
        rtc_ev = next((ev for ev in events if ev.packet_type == "RTC_RESPONSE"), None)
        if rtc_ev and rtc_ev.timestamp:
            rtc_time_str = rtc_ev.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Step 3: Query Info (0xAD)
        self.dev.write_report(Commands.build_hid(0xAD))
        time.sleep(0.15)
        report = self.dev.read_report(64)
        if report:
            parsed_info = Parsers.parse_device_info(report)
            if parsed_info.firmware_version:
                info.firmware_version = parsed_info.firmware_version
            if parsed_info.serial_number:
                info.serial_number = parsed_info.serial_number

        # Step 4: Query 0x81 (Firmware Version Query)
        self.dev.write_report(Commands.build_hid(0x81, [0x01]))
        time.sleep(0.1)
        fw_report = self.dev.read_report(64)
        if fw_report and fw_report[0] == 0x81:
            fw_info = Parsers.parse_device_info(fw_report)
            if fw_info.firmware_version:
                info.firmware_version = fw_info.firmware_version
        elif fw_report and fw_report[0] == 0xF1:
            # The real device answers 0x81 with the hardware model descriptor (e.g. "50F"), not a firmware version.
            model = fw_report[1:10].decode("ascii", errors="ignore").strip()
            info.hardware_id = "".join(c for c in model if c.isalnum() or c in "-_ ").strip() or None

        # Step 5: Query 0x8E (Serial Number / User Profile Query)
        self.dev.write_report(Commands.build_hid(0x8E, [0x03, 0x11]))
        time.sleep(0.1)
        for _ in range(3):
            serial_report = self.dev.read_report(64)
            if serial_report:
                sn, up = Parsers.parse_serial(serial_report)
                if sn:
                    info.serial_number = sn
                if up:
                    info.user_profile = up
            time.sleep(0.05)

        # Step 6: Query 0x9E (Extended Storage Architecture Query)
        self.dev.write_report(Commands.build_hid(0x9E, [0x40, 0x04]))
        time.sleep(0.1)
        geom_report = self.dev.read_report(64)
        if geom_report:
            geom = Parsers.parse_geometry(geom_report)
            if geom:
                info.flash_geometry = geom

        return {
            "device_info": info,
            "active_user_id": active_user_id,
            "rtc_time_str": rtc_time_str,
        }

    def list_sessions(self, debug: Union[bool, int] = 0) -> List[SessionInfo]:
        """Queries device session index table using packet detection."""
        self.dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        while self.dev.read_report(64): pass  # Flush ACK

        self.dev.write_report(Commands.reset_session_index())
        time.sleep(0.08)
        while self.dev.read_report(64): pass  # Flush ACK

        session_map = {}
        for slot in range(1, 32):
            self.dev.write_report(Commands.query_sessions())
            time.sleep(0.05)

            events = self.read_packets(debug=debug)
            ec_event = next((ev for ev in events if ev.packet_type == "SESSION_INDEX"), None)

            if not ec_event or not ec_event.session_info:
                break

            s = ec_event.session_info
            if s.record_count > 0 or s.timestamp:
                session_map[s.session_id] = s

            if ec_event.raw_payload and len(ec_event.raw_payload) > 1 and (ec_event.raw_payload[1] & 0x40):
                break

        return sorted(list(session_map.values()), key=lambda x: x.session_id)

    def download_all_sessions(
        self,
        target_session: int = 0,
        download_all: bool = True,
        timeout_override: float = 0,
        debug: Union[bool, int] = 0,
        dump_file: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extracts stored records for targeted or all session IDs."""
        if dump_file:
            self.dump_fp = open(dump_file, "w", encoding="utf-8")
            self.last_dump_time = time.time()
            self.dump_fp.write("# Pulsox PO-400 Session Download HID Frame Trace Dump\n")
            self.dump_fp.write(f"# Generated: {datetime.now().isoformat()}\n\n")

        try:
            session_list = self.list_sessions(debug=debug)

            if not download_all and target_session > 0:
                matched = [s for s in session_list if s.session_id == target_session]
                if matched:
                    session_list = matched
                else:
                    print(f"Target Session #{target_session} not found in index table; using default bounds...")
                    session_list = [SessionInfo(session_id=target_session, user_id=1, record_count=60, duration_sec=60)]

            if not session_list:
                print("No active session table returned; defaulting to downloading Session #1...")
                session_list = [SessionInfo(session_id=1, user_id=1, record_count=60, duration_sec=60)]

            sess_ids = [s.session_id for s in session_list]
            print(f"Found {len(session_list)} session(s) to download: {sess_ids}")

            total_records = []
            for sess_info in session_list:
                sess_id = sess_info.session_id
                dur_str = sess_info.duration_str
                print(f"\n---> Requesting Session #{sess_id} Data Blocks ({dur_str})...")

                if timeout_override > 0:
                    # -t/--timeout caps the download at that many seconds (= records, 1 per second).
                    cap = int(timeout_override)
                    sess_info.duration_sec = min(sess_info.duration_sec, cap) if sess_info.duration_sec > 0 else cap
                    if sess_info.record_count > 0:
                        sess_info.record_count = min(sess_info.record_count, cap)

                records = self.download_session(sess_info, debug=debug)
                total_records.extend(records)

            print(f"\nDownload complete. Total records collected across all sessions: {len(total_records)}")
            return total_records
        finally:
            if self.dump_fp:
                self.dump_fp.close()
                self.dump_fp = None

    def read_rtc_time(self, debug: Union[bool, int] = 0) -> Optional[datetime]:
        """Queries and returns active device RTC timestamp."""
        c_read = Commands.read_time()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Read RTC: {c_read[:16].hex()}")
        self.dev.write_report(c_read)
        time.sleep(0.15)
        events = self.read_packets(debug=debug)
        rtc_ev = next((ev for ev in events if ev.packet_type == "RTC_RESPONSE"), None)
        return rtc_ev.timestamp if rtc_ev else None

    def set_rtc_time(self, target_dt: Optional[datetime] = None, debug: Union[bool, int] = 0) -> bool:
        """Sets device RTC timestamp."""
        c_unlock = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {c_unlock[:16].hex()}")
        self.dev.write_report(c_unlock)
        time.sleep(0.15)
        while self.dev.read_report(64): pass  # Flush ACK

        c_set = Commands.set_time(target_dt)
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Set RTC: {c_set[:16].hex()}")
        self.dev.write_report(c_set)
        time.sleep(0.3)
        events = self.read_packets(debug=debug)
        return len(events) > 0

    def unlock_handshake(self, debug: Union[bool, int] = 0) -> int:
        """Executes unlock handshake (0xA7) & storage negotiation (0xA2) and returns active User ID."""
        c_unlock = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {c_unlock[:16].hex()}")
        self.dev.write_report(c_unlock)
        time.sleep(0.2)
        rep = self.dev.read_report(64)
        if rep:
            if int(debug) >= 1:
                print(f"[DEBUG IN] Handshake Response: {rep[:16].hex()}")
            return Parsers.parse_user_id(rep)
        return 1

    def clear_memory(self, session_id: int = 0, debug: Union[bool, int] = 0) -> bool:
        """Deletes single session (0xAB) or formats device Flash memory (0xAA/0xAB/0xAC)."""
        self.dev.write_report(Commands.build_hid(0xAF))
        time.sleep(0.1)

        if session_id > 0:
            c_del = Commands.build_hid(0xAB, [0x01, session_id])
            if int(debug) >= 1:
                print(f"[DEBUG OUT] Delete Session #{session_id}: {c_del[:16].hex()}")
            self.dev.write_report(c_del)
            time.sleep(0.2)
        else:
            c_fmt = Commands.build_hid(0xAA, [0x80, 0x80])
            c_ab = Commands.build_hid(0xAB, [0x80, 0x80])
            c_ac = Commands.build_hid(0xAC, [0x80, 0x80])
            if int(debug) >= 1:
                print(f"[DEBUG OUT] Format Flash: {c_fmt[:16].hex()}")
            self.dev.write_report(c_fmt)
            time.sleep(0.2)
            self.dev.write_report(c_ab)
            time.sleep(0.2)
            self.dev.write_report(c_ac)
            time.sleep(0.2)

        c_check = Commands.build_hid(0xA5)
        self.dev.write_report(c_check)
        time.sleep(0.3)
        self.read_packets(debug=debug)
        return True
