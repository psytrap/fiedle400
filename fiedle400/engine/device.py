"""High-level device controller managing streaming, packet detection, and session extraction."""

import queue
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union

from ..protocol import (
    SessionInfo,
    DeviceInfo,
    Parsers,
    Commands,
)
from ..protocol import manual
from .buffer import SerialByteStreamBuffer
from .detector import SerialPacketDetector, DecodedPacket

# The device answers the clock query, but with the same bytes every time (PROTOCOL.md §3.3).
CLOCK_NOT_REPORTED = "not reported by the device"

# T-084: how long a read loop backs off after finding nothing to read. Only applied when a
# read comes back empty -- sleeping unconditionally on every iteration throttles draining below
# the device's burst rate and risks overflowing the kernel's inbound HID report queue (silent
# report loss) on a long, high-volume transfer.
IDLE_READ_SLEEP = 0.005

# T-087: session discovery used to stop dead at 31 slots, undercounting devices with more
# sessions than that. MAX_SESSION_SLOTS is the protocol's own session-index limit: the index
# byte only has 7 usable bits (0..127), the 8th being reserved for command/flag data, not an
# arbitrary safety number. SLOT_READ_ATTEMPTS gives a slow response a few tries before a slot
# is treated as "no more sessions".
MAX_SESSION_SLOTS = 127
SLOT_READ_ATTEMPTS = 3

# T-082/T-085: the `ED 7F` erase reply only confirms the command was accepted, not that the
# flash write has actually committed -- per psytrap, a flat settle delay before the post-erase
# re-list, no poll/retry loop: just give the device more time, then report success or failure
# from that one check.
ERASE_SETTLE_SECONDS = 3.0

# T-088: tests that simulate a device at the OS/fd level (hwsim's HidrawSim, the fake `hid`
# module) set this so no background reader thread starts underneath their single-threaded
# fakes, even when they exercise real CLI code that asks for one. Deliberately not an env var:
# scrub_env() (used throughout the test suite to give cli.main() a clean environment) strips
# every FIEDLE400_-prefixed var, so a flag that has to survive that lives here instead.
SIMULATED_DEVICE_ACTIVE = False


class SerialDeviceEngine:
    """High-level device controller managing streaming, packet detection, and session extraction."""

    def __init__(self, device, background_reader: bool = False):
        self.dev = device
        self.buffer = SerialByteStreamBuffer()
        self.detector = SerialPacketDetector()
        self.dump_fp = None
        self.last_dump_time = None
        self._is_mock = hasattr(device, "responses")  # test doubles script replies; real devices never do
        self.single_erase_unsupported = False  # set by clear_memory, T-074
        self.download_warnings: List[str] = []  # populated by download_session/download_manual, T-094

        # T-088: an opt-in background thread that continuously drains the HID fd into a queue,
        # decoupled from whatever this engine's caller is doing at the time -- removing read-loop
        # pacing entirely as a possible cause of report loss (see T-084). Off by default and
        # forced off for test doubles (`_is_mock`); real CLI command handlers pass
        # `background_reader=True` explicitly. Nothing else may call `self.dev.read_report()`
        # directly once this is on -- everything goes through `_dequeue_report()` instead, so
        # the fd only ever has one reader.
        self._report_queue: "queue.Queue[bytes]" = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_stop = threading.Event()
        self._use_background_reader = background_reader and not self._is_mock and not SIMULATED_DEVICE_ACTIVE
        if self._use_background_reader:
            self._start_reader_thread()

    def _start_reader_thread(self):
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, name="fiedle400-hid-reader", daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
        while not self._reader_stop.is_set():
            try:
                rep = self.dev.read_report(64)
            except Exception:
                break
            if rep:
                self._report_queue.put(rep)
            else:
                time.sleep(0.001)  # avoid busy-spinning the CPU while genuinely idle

    def _stop_reader_thread(self):
        if self._reader_thread is None:
            return
        self._reader_stop.set()
        self._reader_thread.join(timeout=1.0)
        self._reader_thread = None

    def close(self):
        """Stops the background reader thread (if running) and closes the underlying device."""
        self._stop_reader_thread()
        self.dev.close()

    def _dequeue_report(self, timeout: float = 0.0) -> Optional[bytes]:
        """Returns the next HID report, or None if none is available within `timeout` seconds.

        With the background reader active, reports already pulled off the fd are served from
        its queue; otherwise (including all test doubles) this reads the driver directly, exactly
        as every call site here did before T-088 -- so nothing changes unless a caller explicitly
        opts in."""
        if not getattr(self, "_use_background_reader", False):
            return self.dev.read_report(64)
        try:
            return self._report_queue.get(block=True, timeout=timeout) if timeout > 0 else self._report_queue.get_nowait()
        except queue.Empty:
            return None

    def _flush_before_command(self, debug: Union[bool, int] = 0):
        """Drains whatever is already queued/buffered before writing a new command (T-090).

        Unifies what was ~9 separate `while self._dequeue_report(): pass` copies into one
        helper -- same behavior as before (just drains until nothing is immediately available),
        no retry budget or timing changed. Does NOT make this a true synchronization point
        against the T-088 background reader thread still filling the queue concurrently --
        that race is tracked separately (T-091), deferred rather than solved here.
        """
        drained = 0
        while self._dequeue_report():
            drained += 1
        if int(debug) >= 1 and drained:
            print(f"[DEBUG] _flush_before_command() dropped {drained} stale report(s)")

    def read_raw_report(self, timeout: float = 0.0) -> Optional[bytes]:
        """Reads one raw HID report with no packet decoding -- for one-off protocol steps (like
        the CLI's initial handshake probe) that need the device's immediate reply directly."""
        return self._dequeue_report(timeout=timeout)

    def _sleep(self, seconds: float):
        if not getattr(self, "_is_mock", False):
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
        report = self._dequeue_report()
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

    def wait_for_packet(
        self,
        expected_types: Union[str, tuple, list, set],
        base_timestamp: Optional[datetime] = None,
        timeout: float = 1.0,
        debug: Union[bool, int] = 0,
    ) -> Optional[DecodedPacket]:
        """Reads packets until one with a `packet_type` in `expected_types` arrives, or
        `timeout` seconds pass with no match -- the "wait for the expected reply, discard
        anything else" half of a clean request/response exchange (T-089). Every decoded
        event that doesn't match is simply dropped, same as what every call site below did
        by hand before this existed; it does not resend the request on its own -- callers
        still write their own command first.
        """
        if isinstance(expected_types, str):
            expected_types = (expected_types,)
        deadline = time.time() + timeout
        while time.time() < deadline:
            events = self.read_packets(base_timestamp, debug=debug)
            match = next((ev for ev in events if ev.packet_type in expected_types), None)
            if match is not None:
                return match
            if not events:
                self._sleep(IDLE_READ_SLEEP)
        return None

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
            if not events:
                # T-084: only back off when there was nothing to read -- sleeping unconditionally
                # here throttles draining below the device's burst rate and risks overflowing the
                # kernel's inbound HID report queue (silent report loss) on a busy stream.
                self._sleep(IDLE_READ_SLEEP)

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
            rep = self._dequeue_report()
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
                self._sleep(IDLE_READ_SLEEP)

        if int(debug) >= 1:
            print(f"[DEBUG IN] Drained {drained_reports} residual HID reports (quiet period: 200ms verified).")

        self.buffer.clear()
        return eb_count

    def download_session(self, sess_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """Downloads stored oximetry session records using SerialPacketDetector engine."""
        if sess_info.manual:
            return self.download_manual(sess_info, debug=debug)
        sess_id = sess_info.session_id
        duration_sec = sess_info.duration_seconds
        base_timestamp = sess_info.timestamp or datetime.now()

        # Step 1: Flush stale reports & send unlock handshake + storage init
        self._flush_before_command(debug=debug)

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

        self._flush_before_command(debug=debug)  # Flush ACK

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
        # (RELEASE_PLAN.md T6): each request continues where the records so far end. One record
        # is one stored sample (T-075), so the offset is the record count. A reply that adds no record
        # (the end marker at offset == stored samples, or silence past it) ends the download.
        for _window in range(4096):
            if len(sess_records) >= target_records:
                break
            page_idx = len(sess_records)
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
                if not events:
                    # T-084: only back off when nothing came back -- an unconditional sleep here
                    # caps drain rate below the device's burst rate during a long transfer, which
                    # risks the kernel's inbound HID report queue overflowing (silent report loss,
                    # seen as CORRUPT_FRAME/sequence gaps downstream).
                    self._sleep(IDLE_READ_SLEEP)

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
                    if not events:
                        # T-084: see the matching comment in the SpO2 page loop above.
                        self._sleep(IDLE_READ_SLEEP)

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
        neg_res = self._dequeue_report()
        if neg_res:
            active_user_id = Parsers.parse_user_id(neg_res)

        # Step 2: Query RTC Clock (0x82)
        self.dev.write_report(Commands.read_time())
        time.sleep(0.15)
        events = self.read_packets(debug=debug)
        if any(ev.packet_type == "RTC_RESPONSE" for ev in events):
            rtc_time_str = CLOCK_NOT_REPORTED

        # Step 3: Query Info (0xAD)
        self.dev.write_report(Commands.build_hid(0xAD))
        time.sleep(0.15)
        report = self._dequeue_report()
        if report:
            parsed_info = Parsers.parse_device_info(report)
            if parsed_info.firmware_version:
                info.firmware_version = parsed_info.firmware_version
            if parsed_info.serial_number:
                info.serial_number = parsed_info.serial_number

        # Step 4: Query 0x81 (Firmware Version Query)
        self.dev.write_report(Commands.build_hid(0x81, [0x01]))
        time.sleep(0.1)
        fw_report = self._dequeue_report()
        if fw_report and fw_report[0] == 0x81:
            fw_info = Parsers.parse_device_info(fw_report)
            if fw_info.firmware_version:
                info.firmware_version = fw_info.firmware_version
        elif fw_report and fw_report[0] == 0xF1:
            # The real device answers 0x81 with the hardware model descriptor (e.g. "50F"), not a firmware version.
            model = fw_report[1:10].decode("ascii", errors="ignore").strip()
            info.hardware_id = "".join(c for c in model if c.isalnum() or c in "-_ ").strip() or None

        # Step 5: Query 0x8E (Serial Number / User Profile Query)
        # T-089: NOT migrated to wait_for_packet(). The detector's SERIAL_PROFILE branch only
        # fires on buf[0] == 0x8E (detector.py ~line 291), but the real reply's first byte is
        # 0xF1 or 0xFE -- which the DEVICE_INFO branch above it (buf[0] in [0x81, 0xFE, 0xF1,
        # 0xF0], ~line 276) catches first and parses with parse_device_info(), which never
        # extracts user_profile. So the 16-byte detector path cannot reach parse_serial() for
        # this reply at all; the two paths are not equivalent. Confirmed by a real test
        # regression (lost User Profile String) when this was tried. Stays a direct read.
        self.dev.write_report(Commands.build_hid(0x8E, [0x03, 0x11]))
        time.sleep(0.1)
        for _ in range(3):
            serial_report = self._dequeue_report()
            if serial_report:
                sn, up = Parsers.parse_serial(serial_report)
                if sn:
                    info.serial_number = sn
                if up:
                    info.user_profile = up
            time.sleep(0.05)

        # Step 6: Query 0x9E (Extended Storage Architecture Query)
        # T-089: migrated onto wait_for_packet() -- Parsers.parse_geometry() only ever reads
        # offsets 0..2, so the detector's 16-byte GEOMETRY_INFO chunk and the old 64-byte
        # direct parse are equivalent. A/B-tested against real hardware: both report "not
        # reported by the device" for this field (pre-existing, not a migration regression).
        self.dev.write_report(Commands.build_hid(0x9E, [0x40, 0x04]))
        geom_ev = self.wait_for_packet("GEOMETRY_INFO", timeout=0.1, debug=debug)
        if geom_ev and geom_ev.device_info and geom_ev.device_info.flash_geometry:
            info.flash_geometry = geom_ev.device_info.flash_geometry

        return {
            "device_info": info,
            "active_user_id": active_user_id,
            "rtc_time_str": rtc_time_str,
        }

    def list_sessions(self, debug: Union[bool, int] = 0, attempts: int = 3, retry_delay: float = 0.3) -> List[SessionInfo]:
        """Queries device session index table using packet detection.

        An empty result is known to show up sporadically even when the device does have
        stored sessions (a transient/first-command USB hiccup, T-078) -- so an empty read is
        retried up to `attempts` times, a short `retry_delay` apart, before it's trusted and
        returned. A real empty device (no sessions at all) retries the same number of times
        and still correctly comes back empty, so this only protects against false negatives.
        """
        for attempt in range(1, attempts + 1):
            sessions = self._list_sessions_once(debug=debug)
            if sessions:
                return sessions
            if attempt < attempts:
                if int(debug) >= 1:
                    print(f"[DEBUG] list_sessions came back empty (attempt {attempt}/{attempts}), retrying...")
                self._sleep(retry_delay)
        return sessions

    def _list_sessions_once(self, debug: Union[bool, int] = 0) -> List[SessionInfo]:
        self.dev.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        self._flush_before_command(debug=debug)  # Flush ACK

        self.dev.write_report(Commands.reset_session_index())
        time.sleep(0.08)
        self._flush_before_command(debug=debug)  # Flush ACK

        session_map = {}
        # T-087: this upper bound is a safety net against a runaway loop, not a real limit on
        # how many sessions a device can hold -- actual termination is the 0x40 terminator bit
        # below, or SLOT_READ_ATTEMPTS misses in a row (a device with no more sessions to report).
        for slot in range(1, MAX_SESSION_SLOTS + 1):
            self.dev.write_report(Commands.query_sessions())
            # SLOT_READ_ATTEMPTS misses in a row at 0.05s apiece -- same total budget as before
            # this used wait_for_packet(), just polled more finely instead of in 3 fixed steps.
            ec_event = self.wait_for_packet("SESSION_INDEX", timeout=SLOT_READ_ATTEMPTS * 0.05, debug=debug)

            if not ec_event or not ec_event.session_info:
                break

            s = ec_event.session_info
            if s.record_count > 0 or s.timestamp:
                session_map[s.session_id] = s

            if ec_event.raw_payload and len(ec_event.raw_payload) > 1 and (ec_event.raw_payload[1] & 0x40):
                break

        sessions = sorted(list(session_map.values()), key=lambda x: x.session_id)
        if not sessions:
            # A device in Manual recording mode lists nothing here; its one recording has its own
            # header query (PROTOCOL.md 3.14, T-042). Asked only when the Auto list is empty.
            header = self.read_manual_header(debug=debug)
            if header is not None and header.samples > 0:
                sessions.append(SessionInfo(session_id=1, user_id=1, record_count=header.samples,
                                            duration_sec=header.samples, timestamp=header.start,
                                            raw_samples=header.samples, manual=True))
        return sessions

    # --- Manual mode (PROTOCOL.md 3.14, T-042) ---------------------------------------------------
    def _manual_frames(self, done, timeout: float = 1.0, quiet: float = 0.3, debug: Union[bool, int] = 0) -> List[bytes]:
        """Reads reports until done(frames) is true, nothing new came for `quiet` s, or `timeout` s passed."""
        got: List[bytes] = []
        start = last = time.time()
        while time.time() - start < timeout and time.time() - last < quiet:
            report = self._dequeue_report()
            if report:
                self._log_dump("IN", report, "manual mode")
                if int(debug) >= 2:
                    print(f"[DEBUG IN] Raw HID Frame ({len(report)} bytes): {report.hex()}")
                new = manual.frames([report])
                if new:
                    got.extend(new)
                    last = time.time()
                    if done(got):
                        break
            else:
                self._sleep(IDLE_READ_SLEEP)
        return got

    def read_manual_header(self, debug: Union[bool, int] = 0) -> Optional[manual.ManualHeader]:
        """Asks for the Manual-mode recording's header (`A0`); None when the device does not answer."""
        self._flush_before_command(debug=debug)
        self._write_report(manual.header_query(), "Manual header (0xA0)")
        got = self._manual_frames(lambda fr: any(f[0] == manual.HEADER for f in fr), timeout=0.5, debug=debug)
        header = next((manual.parse_header(f) for f in got if f[0] == manual.HEADER), None)
        if int(debug) >= 1:
            print(f"[DEBUG IN] Manual header: {header}")
        return header

    MAX_CONSECUTIVE_STALLS = 20  # T-094: give up only after this many *consecutive* no-progress resumes

    def _manual_series(self, opcode: int, reply: int, samples: int, debug: Union[bool, int] = 0) -> List[int]:
        """One series, 27 values per subframe. A missing subframe is asked for again from where
        the series broke off, as SpO2 Assistant does (`9N 7F`, then `9N 00` from that subframe).

        T-094: a batch of frames from one read round is no longer abandoned at the first
        out-of-order subframe. On real hardware, subframes routinely arrive with small gaps
        (e.g. 0,1,2,4,5,7,8 -- 3 and 6 missing) even outside a resume, and after a resume the
        freshly-requested subframe often arrives interleaved with stale ones still in flight
        from before the stop took effect, in any order. The old code treated the *first*
        out-of-order frame as "the rest of this batch is junk" and broke out of the loop,
        permanently discarding the actually-needed in-order frame sitting right after it --
        which is why real downloads stalled almost immediately and never recovered even with
        many resumes.

        A subframe that arrives ahead of `expected` is now cached (by subframe number) instead
        of being thrown away -- it was real, already-received data; discarding it just meant
        re-requesting it later over another explicit stop/resume round-trip, which is what made
        every gap costly. `expected` is drained against that cache (possibly several subframes
        at once, including ones unlocked earlier in the same batch regardless of arrival order)
        before falling back to asking the device again.

        A resume (stop + re-request) is only issued when a whole round made zero progress, and
        gives up only after `MAX_CONSECUTIVE_STALLS` *consecutive* no-progress rounds, reset on
        any progress -- not a fixed total budget that a single early gap could exhaust."""
        values: List[int] = []
        self._write_report(manual.series_request(opcode), f"Manual series (0x{opcode:02X})")
        consecutive_stalls = 0
        pending: Dict[int, List[int]] = {}  # subframe seq -> decoded values, received ahead of `expected`
        while len(values) < samples:
            got = self._manual_frames(
                lambda fr: len(values) + manual.SAMPLES_PER_SUBFRAME * sum(f[0] == reply for f in fr) >= samples,
                timeout=2.0, debug=debug)
            progressed = False
            for f in (f for f in got if f[0] == reply):
                expected = len(values) // manual.SAMPLES_PER_SUBFRAME
                seq = manual.subframe_seq(f)
                if seq == expected:
                    values.extend(manual.decode_subframe(f))
                    progressed = True
                elif seq > expected and seq not in pending:
                    pending[seq] = manual.decode_subframe(f)
                # seq < expected: a stale repeat of a subframe we already have -- nothing to do.
            expected = len(values) // manual.SAMPLES_PER_SUBFRAME
            while expected in pending:
                values.extend(pending.pop(expected))
                progressed = True
                expected = len(values) // manual.SAMPLES_PER_SUBFRAME
            if len(values) >= samples:
                break
            if progressed:
                consecutive_stalls = 0
                continue  # the stream is flowing -- keep reading, no need to interrupt it
            consecutive_stalls += 1
            if consecutive_stalls > self.MAX_CONSECUTIVE_STALLS:
                break
            expected = len(values) // manual.SAMPLES_PER_SUBFRAME
            if int(debug) >= 1:
                print(f"[DEBUG OUT] Manual series 0x{opcode:02X}: asking again from subframe {expected} "
                      f"(stall {consecutive_stalls}/{self.MAX_CONSECUTIVE_STALLS})")
            self._write_report(manual.series_end(opcode), f"Manual series stop (0x{opcode:02X} 7F)")
            self._write_report(manual.series_request(opcode, expected), f"Manual series (0x{opcode:02X}) from {expected}")
            if not got:
                self._sleep(0.05)
        return values[:samples]

    def download_manual(self, sess_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """Downloads the Manual-mode recording: SpO2 (`A3`), ack (`A7 01`), pulse (`A2`), ack (`A7 00`),
        then `A3 7F` / `A2 7F` to end. Read-only: nothing here erases the recording."""
        samples = sess_info.record_count
        base_timestamp = sess_info.timestamp or datetime.now()
        self._flush_before_command(debug=debug)
        self._write_report(bytes([0x80]) + bytes(63), "Stop live stream (0x80)")
        self._manual_frames(lambda fr: False, timeout=0.1, quiet=0.05)

        spo2 = self._manual_series(manual.SPO2_REQUEST, manual.SPO2_DATA, samples, debug=debug)
        self._write_report(manual.block_ack(True), "Manual SpO2 done (0xA7 01)")
        self._manual_frames(lambda fr: any(f[0] == manual.BLOCK_ACK for f in fr), timeout=0.3)
        pulse = self._manual_series(manual.PULSE_REQUEST, manual.PULSE_DATA, samples, debug=debug)
        self._write_report(manual.block_ack(False), "Manual pulse done (0xA7 00)")
        self._manual_frames(lambda fr: any(f[0] == manual.BLOCK_ACK for f in fr), timeout=0.3)
        self._write_report(manual.series_end(manual.SPO2_REQUEST), "Manual end (0xA3 7F)")
        self._write_report(manual.series_end(manual.PULSE_REQUEST), "Manual end (0xA2 7F)")

        out = []
        for i, (s, p) in enumerate(manual.records(spo2, pulse, samples)):
            out.append({
                "session_id": sess_info.session_id,
                "user_id": sess_info.user_id,
                "block_id": 1,
                "seq": i // manual.SAMPLES_PER_SUBFRAME,
                "timestamp": (base_timestamp + timedelta(seconds=i)).isoformat(),
                "spo2": s,
                "heart_rate": p,
                "flags": "ok" if s is not None else "probe-out",
            })
        missing = samples - min(len(spo2), len(pulse))
        print(f"\nManual recording download complete ({len(out)} records).")
        if missing > 0:
            warning = (f"the device sent {missing} sample(s) fewer than its header announced; "
                       f"those seconds are empty. Download it again.")
            print(f"WARNING: {warning}")
            self.download_warnings.append(warning)
        return out

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

    def read_rtc_time(self, debug: Union[bool, int] = 0) -> Optional[bytes]:
        """Sends the clock query and returns the raw 0xF2 reply, or None if none came.

        The reply has been the same 8 bytes in every recording (PROTOCOL.md §3.3), so it
        is returned as is rather than decoded into a time.
        """
        c_read = Commands.read_time()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Read RTC: {c_read[:16].hex()}")
        self.dev.write_report(c_read)
        rtc_ev = self.wait_for_packet("RTC_RESPONSE", timeout=0.15, debug=debug)
        return rtc_ev.raw_payload if rtc_ev else None

    def set_rtc_time(self, target_dt: Optional[datetime] = None, debug: Union[bool, int] = 0) -> bool:
        """Sets device RTC timestamp."""
        c_unlock = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {c_unlock[:16].hex()}")
        self.dev.write_report(c_unlock)
        time.sleep(0.15)
        self._flush_before_command(debug=debug)  # Flush ACK

        c_set = Commands.set_time(target_dt)
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Set RTC: {c_set[:16].hex()}")
        self.dev.write_report(c_set)
        time.sleep(0.3)
        events = self.read_packets(debug=debug)
        return len(events) > 0

    def unlock_handshake(self, debug: Union[bool, int] = 0) -> int:
        """Executes unlock handshake (0xA7) & storage negotiation (0xA2) and returns active User ID.

        T-089: left as a raw, unfiltered read rather than migrated onto wait_for_packet(). The
        detector has no packet type for this reply, and -- unlike the erase/session/RTC replies
        -- there's no other packet type it could realistically be confused with in practice, so
        the risk this ticket exists to address isn't really present here. Revisit only if that
        stops being true.
        """
        c_unlock = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {c_unlock[:16].hex()}")
        self.dev.write_report(c_unlock)
        time.sleep(0.2)
        rep = self._dequeue_report()
        if rep:
            if int(debug) >= 1:
                print(f"[DEBUG IN] Handshake Response: {rep[:16].hex()}")
            return Parsers.parse_user_id(rep)
        return 1

    def clear_memory(self, session_id: int = 0, debug: Union[bool, int] = 0) -> bool:
        """Erases one recording (`session_id` > 0) or all of them -- dispatches to `_clear_auto()`
        or `_clear_manual()` depending on which kind of recording `session_id` (or "erase all")
        actually refers to on the device right now.

        A Manual-mode recording (there is at most one, T-042) is erased separately, with the
        unconfirmed `A1`/`D1` sequence from PROTOCOL.md 3.14 G (T-072); everything else goes
        through the Auto-mode `9D` sequence (PROTOCOL.md 3.13).
        """
        before = self.list_sessions(debug=debug)
        manual_target = next((s for s in before if s.manual and (session_id <= 0 or s.session_id == session_id)), None)
        if manual_target is not None:
            return self._clear_manual(debug=debug)
        return self._clear_auto(session_id, before, debug=debug)

    def _clear_auto(self, session_id: int, before: List[SessionInfo], debug: Union[bool, int] = 0) -> bool:
        """Erases Auto-mode recording(s): `9D 7F 7F 7F 7F` for all (`_clear_auto_all`), or for
        one, `9D 7F 02 [user] [entry]` (pulse series) then `9D 7F 01 [user] [entry]` (SpO2
        series) once the device has confirmed the first (`_clear_auto_entry`), as the vendor
        tool does.

        Like the vendor tool, it lists the recordings (`before`, from `clear_memory()`) and opens
        the storage transfer (`9D 02`) first -- unconditionally (T-092): even when nothing in
        `before` matches `session_id`, it still goes through the same wire sequence rather than
        returning without ever talking to the device. For "erase all" that's harmless either way
        (there's always a valid `delete_all` to send, erasing nothing on an already-empty device
        is a no-op) -- `_clear_auto_all()` runs regardless of whether `targets` is empty. For a
        single `session_id` that matches nothing, there is no `(user_id, session_id)` pair to
        build a `delete_entry` command from, so that one step is genuinely not possible to send;
        the transfer is still opened, the delete step is just skipped.

        Afterwards it lists the recordings again: returns True only if what should be gone is
        gone, regardless of what the erase reply status bytes claimed. For a no-match single
        `session_id`, "gone" can't be judged by timestamp (nothing was ever targeted), so it
        falls back to the original check: no Auto-mode session with that id exists afterward.
        """
        targets = [s for s in before if not s.manual and (session_id <= 0 or s.session_id == session_id)]
        if int(debug) >= 1 and not targets:
            print("[DEBUG] Nothing matches the erase target -- opening the transfer anyway.")

        self._write_report(Commands.storage_init(), "Storage Init (0x9D 0x02)")
        self._sleep(0.05)
        self._flush_before_command(debug=debug)
        if session_id > 0:
            if targets:
                self._clear_auto_entry(targets[0], debug=debug)
            elif int(debug) >= 1:
                print(f"[DEBUG] No entry for session {session_id} to delete -- skipping the delete step.")
        else:
            self._clear_auto_all(debug=debug)

        self._sleep(ERASE_SETTLE_SECONDS)
        after = self.list_sessions(debug=debug)
        if session_id > 0 and not targets:
            return not any(not s.manual and s.session_id == session_id for s in after)
        gone = {(t.user_id, t.session_id) for t in targets}
        left = [s for s in after if not s.manual and (s.user_id, s.session_id) in gone]
        if session_id > 0:
            # Entries are renumbered after a delete; compare start times, not numbers.
            left = [s for s in after if not s.manual and s.timestamp == targets[0].timestamp]
        return not left

    def _clear_auto_all(self, debug: Union[bool, int] = 0) -> None:
        """Sends the "erase all" step (`9D 7F`) and waits for its erase-reply status. Just the
        one step -- verification (did it actually disappear) happens back in `_clear_auto()`."""
        cmd, desc = Commands.delete_all(), "Delete All (0x9D 0x7F)"
        if int(debug) >= 1:
            print(f"[DEBUG OUT] {desc}: {cmd[:16].hex()}")
        self._write_report(cmd, desc)
        self._sleep(0.5)
        status = self._erase_status()
        if int(debug) >= 1:
            print(f"[DEBUG] Erase reply status: {'none' if status is None else status}")

    def _clear_auto_entry(self, target: SessionInfo, debug: Union[bool, int] = 0) -> None:
        """Sends the two-step single-entry delete for `target` -- pulse series (`9D 7F 02 [user]
        [entry]`), then SpO2 series (`9D 7F 01 [user] [entry]`) -- each gated on the previous
        step's erase-reply status, as the vendor tool does. If the device does not answer the
        first step with a real erase reply (a real PO-400 answers it with the generic `F0 70`
        ack only and erases nothing, T-074), this stops there and sets
        `single_erase_unsupported` instead of sending the second step.
        """
        steps = [(Commands.delete_entry(target.user_id, target.session_id, series),
                  f"Delete user {target.user_id} entry {target.session_id}, series {series} (0x9D 0x7F 0x0{series})")
                 for series in (2, 1)]
        for n, (cmd, desc) in enumerate(steps):
            if int(debug) >= 1:
                print(f"[DEBUG OUT] {desc}: {cmd[:16].hex()}")
            self._write_report(cmd, desc)
            self._sleep(0.5)
            status = self._erase_status()
            if int(debug) >= 1:
                print(f"[DEBUG] Erase reply status: {'none' if status is None else status}")
            if status not in (None, 0):
                break
            if status is None and n == 0:
                self.single_erase_unsupported = True
                break

    def _clear_manual(self, debug: Union[bool, int] = 0) -> bool:
        """Erases the Manual-mode recording with SpO2.exe's own, unconfirmed `A1`/`D1` sequence
        (PROTOCOL.md 3.14 G, T-072): `A1 00`, then `A1 01` once the device confirms the first.
        `A1 04` (third series) is not sent -- Manual mode has no known way to tell whether it
        applies. Verified the same way as the Auto-mode path: by listing again afterwards.
        """
        for step in (0, 1):
            desc = f"Manual delete step 0x{step:02X} (0xA1)"
            if int(debug) >= 1:
                print(f"[DEBUG OUT] {desc}: {manual.delete_step(step)[:16].hex()}")
            status = self._manual_delete_step(step, debug=debug)
            if int(debug) >= 1:
                print(f"[DEBUG] Erase reply status: {'none' if status is None else status}")
            if status not in (None, 0):
                break

        after = self.list_sessions(debug=debug)
        return not any(s.manual for s in after)

    def _manual_delete_step(self, step: int, debug: Union[bool, int] = 0) -> Optional[int]:
        """Sends one Manual-mode erase step (`A1`) and returns its `D1` reply's status byte
        (0 = done), or None if no reply came."""
        self._flush_before_command(debug=debug)
        self._write_report(manual.delete_step(step), f"Manual delete step 0x{step:02X} (0xA1)")
        got = self._manual_frames(lambda fr: any(f[0] == manual.DELETE_REPLY for f in fr), timeout=1.0, debug=debug)
        reply = next((f for f in got if f[0] == manual.DELETE_REPLY), None)
        if reply is None:
            return None
        parsed = manual.parse_delete_reply(reply)
        return parsed[1] if parsed else None

    def _erase_status(self, timeout: float = 1.0, quiet: float = 0.3) -> Optional[int]:
        """Reads what the device sent after an erase command and returns the status byte of its
        `ED 7F [series] [user] [entry] [status] [chk]` reply (0 = done), or None if none came.

        T-089: loops for up to `timeout` seconds, or until `quiet` seconds pass with nothing
        new -- a single non-blocking empty read used to end the search immediately, which only
        worked because the caller was the fd's only reader; with the T-088 background reader
        thread, an empty poll can land in a real gap between two reports still in flight, not
        "nothing is coming". The `ED 7F` reply has no packet type in the detector, so this
        stays a raw-byte scan rather than going through `wait_for_packet()`.
        """
        status = None
        start = last = time.time()
        while time.time() - start < timeout and time.time() - last < quiet:
            rep = self._dequeue_report()
            if not rep:
                self._sleep(IDLE_READ_SLEEP)
                continue
            last = time.time()
            r = bytes(rep)
            i = r.find(b"\xed\x7f")
            if i >= 0 and i + 7 <= len(r) and (sum(r[i:i + 6]) & 0x7F) == r[i + 6]:
                status = r[i + 5]
        return status
