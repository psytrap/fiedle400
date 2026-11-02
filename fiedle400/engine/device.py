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
        self.device = device
        self.buffer = SerialByteStreamBuffer()
        self.detector = SerialPacketDetector()
        self.dump_file = None
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
                report = self.device.read_report(64)
            except Exception:
                break
            if report:
                self._report_queue.put(report)
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
        self.device.close()

    def _dequeue_report(self, timeout: float = 0.0) -> Optional[bytes]:
        """Returns the next HID report, or None if none is available within `timeout` seconds.

        With the background reader active, reports already pulled off the fd are served from
        its queue; otherwise (including all test doubles) this reads the driver directly, exactly
        as every call site here did before T-088 -- so nothing changes unless a caller explicitly
        opts in."""
        if not getattr(self, "_use_background_reader", False):
            return self.device.read_report(64)
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
        if self.dump_file is None:
            return
        now = time.time()
        date_time_text = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        delta_seconds = (now - self.last_dump_time) if self.last_dump_time else 0.0
        self.last_dump_time = now
        hex_text = report_bytes.hex()
        line = f"[{date_time_text}] (Δt={delta_seconds:.3f}s) [{direction:<3}] ({len(report_bytes):>2}B): {hex_text}"
        if summary:
            line += f" | {summary}"
        self.dump_file.write(line + "\n")
        self.dump_file.flush()

    def _write_report(self, report_bytes: bytes, description: str = ""):
        self._log_dump("OUT", report_bytes, description)
        return self.device.write_report(report_bytes)

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

        if self.dump_file is not None:
            summary_parts = []
            if events:
                for event in events:
                    summary_parts.append(f"{event.packet_type} (blk={event.block_id}, seq={event.sequence}, SpO2={event.spo2}, HR={event.heart_rate}, status={event.status_text})")
            summary_text = "; ".join(summary_parts) if summary_parts else "RAW_REPORT"
            self._log_dump("IN", report, summary_text)

        if debug_level >= 1 and events:
            for event in events:
                raw_text = event.raw_payload.hex() if event.raw_payload else "None"
                spo2_text = f"{event.spo2}%" if event.spo2 is not None else "N/A"
                heart_rate_text = f"{event.heart_rate} bpm" if event.heart_rate is not None else "N/A"
                print(f"[DEBUG IN] Packet Type={event.packet_type:<15} | Payload={raw_text:<24} | SpO2={spo2_text:<6} | HR={heart_rate_text:<8} | Status={event.status_text}")
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
            match = next((event for event in events if event.packet_type in expected_types), None)
            if match is not None:
                return match
            if not events:
                self._sleep(IDLE_READ_SLEEP)
        return None

    def wait_for_eb_stream(self, target_count: int = 10, max_timeout: float = 10.0, debug: Union[bool, int] = 0) -> int:
        """Enables periodic streaming (0x9B) and listens until target_count (default 10) 0xEB messages have been reported before starting other communication."""
        stream_command = Commands.query_data_stream()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Enable Periodic Telemetry (0x9B): {stream_command[:16].hex()}")
            print(f"[DEBUG OUT] Waiting for {target_count} 0xEB live stream messages before starting communication...")

        self._write_report(stream_command, "Enable Telemetry (0x9B)")
        self._sleep(0.05)

        eb_count = 0
        start_time = time.time()
        empty_count = 0

        while eb_count < target_count and (time.time() - start_time < max_timeout):
            events = self.read_packets(debug=debug)
            if not events:
                empty_count += 1
                if empty_count > 10:  # Exit early if device/mock returns no packets
                    break
            else:
                empty_count = 0
                for event in events:
                    if event.packet_type == "LIVE_STREAM" or (event.raw_payload and event.raw_payload[0] == 0xEB):
                        eb_count += 1
                        if eb_count >= target_count:
                            break
            if not events:
                # T-084: only back off when there was nothing to read -- sleeping unconditionally
                # here throttles draining below the device's burst rate and risks overflowing the
                # kernel's inbound HID report queue (silent report loss) on a busy stream.
                self._sleep(IDLE_READ_SLEEP)

        if int(debug) >= 1:
            print(f"[DEBUG IN] Received {eb_count}/{target_count} 0xEB stream messages (elapsed: {time.time() - start_time:.2f}s).")

        # Turn off periodic messages after target_count 0xEB messages arrived
        stop_command = Commands.stop_data_stream()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Disable Periodic Telemetry (0x9B Stop): {stop_command[:16].hex()}")
        self._write_report(stop_command, "Disable Telemetry (0x9B Stop)")

        # Drain residual stream reports until no new messages arrive
        drain_start = time.time()
        last_message_time = time.time()
        drained_reports = 0
        drain_empty_count = 0
        while (time.time() - last_message_time < 0.20) and (time.time() - drain_start < 2.0):
            report = self._dequeue_report()
            if report:
                drain_empty_count = 0
                if report[0] == 0xEB or (len(report) >= 3 and report[2] == 0xEB):
                    drained_reports += 1
                    last_message_time = time.time()
                else:
                    self.buffer.write(report)
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

    def download_session(self, session_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """Downloads stored oximetry session records using SerialPacketDetector engine."""
        if session_info.manual:
            return self.download_manual(session_info, debug=debug)
        session_id = session_info.session_id
        duration_seconds = session_info.duration_seconds
        base_timestamp = session_info.timestamp or datetime.now()

        # Step 1: Flush stale reports & send unlock handshake + storage init
        self._flush_before_command(debug=debug)

        unlock_command = Commands.unlock_handshake()
        init_command = Commands.storage_init()

        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {unlock_command[:16].hex()}")
        self._write_report(unlock_command, "Unlock Handshake (0xA7/0xA2)")
        self._sleep(0.05)

        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Storage Init: {init_command[:16].hex()}")
        self._write_report(init_command, "Storage Init (0x9D 0x02)")
        self._sleep(0.05)

        self._flush_before_command(debug=debug)  # Flush ACK

        SerialPacketDetector.reset_decoder_state()

        session_records = []
        total_packets = 0
        total_sequence_gaps = 0
        corrupt_frames = 0
        target_records = session_info.record_count if session_info.record_count > 0 else (duration_seconds if duration_seconds > 0 else 600)

        last_block_spo2: Optional[int] = None
        last_block_heart_rate:   Optional[int] = None

        block_spo2_packets = []
        block_heart_rate_packets = []

        def flush_block_buffers():
            nonlocal last_block_spo2, last_block_heart_rate
            if not block_spo2_packets and not block_heart_rate_packets:
                return

            pair_count = max(len(block_spo2_packets), len(block_heart_rate_packets))
            for i in range(pair_count):
                spo2_event = block_spo2_packets[i] if i < len(block_spo2_packets) else None
                heart_rate_event = block_heart_rate_packets[i] if i < len(block_heart_rate_packets) else None

                flags = spo2_event.status_text if spo2_event else (heart_rate_event.status_text if heart_rate_event else "ok")
                is_probe_out = "probe-out" in flags or "searching" in flags

                if is_probe_out:
                    spo2_value = None
                    heart_rate_value = None
                else:
                    spo2_value = spo2_event.spo2 if (spo2_event and spo2_event.spo2 is not None) else last_block_spo2
                    heart_rate_value = heart_rate_event.heart_rate if (heart_rate_event and heart_rate_event.heart_rate is not None) else last_block_heart_rate

                    if spo2_value is not None: last_block_spo2 = spo2_value
                    if heart_rate_value is not None: last_block_heart_rate = heart_rate_value

                block_id = spo2_event.block_id if spo2_event else (heart_rate_event.block_id if heart_rate_event else 1)
                sequence = spo2_event.sequence if spo2_event else (heart_rate_event.sequence if heart_rate_event else 0)

                session_records.append({
                    "session_id": session_id,
                    "user_id": session_info.user_id,
                    "block_id": block_id,
                    "sequence": sequence,
                    "timestamp": (base_timestamp + timedelta(seconds=len(session_records))).isoformat(),
                    "spo2": spo2_value,
                    "heart_rate": heart_rate_value,
                    "flags": flags,
                })
                if len(session_records) >= target_records:
                    break
            block_spo2_packets.clear()
            block_heart_rate_packets.clear()

        # The "page" argument of a 0x9D 0x04 read is the sample offset at which the reply starts
        # (RELEASE_PLAN.md T6): each request continues where the records so far end. One record
        # is one stored sample (T-075), so the offset is the record count. A reply that adds no record
        # (the end marker at offset == stored samples, or silence past it) ends the download.
        for _window in range(4096):
            if len(session_records) >= target_records:
                break
            page_index = len(session_records)
            records_before = len(session_records)
            SerialPacketDetector.reset_decoder_state()

            page_received_packets = False
            flash_sentinel_hit = False

            # Query SpO2 page
            spo2_command = Commands.session_page(1, session_id, page_index, session_info.user_id)
            if int(debug) >= 1:
                print(f"[DEBUG OUT] Serial Engine SpO2 Page #{page_index}: {spo2_command[:16].hex()}")
            self._write_report(spo2_command, f"Request SpO2 Page #{page_index}")
            self._sleep(0.05)

            page_start = time.time()
            last_packet_time = time.time()
            retries = 0

            while True:
                now = time.time()
                if not page_received_packets and (now - page_start > 0.35):
                    if retries < 2 and not self._is_mock:
                        retries += 1
                        page_start = now
                        if int(debug) >= 1:
                            print(f"[DEBUG OUT] Retrying SpO2 Page #{page_index} (attempt {retries+1})")
                        self._write_report(spo2_command, f"Retry SpO2 Page #{page_index}")
                    else:
                        break
                if page_received_packets and (now - last_packet_time > 0.25):
                    break
                if len(session_records) >= target_records or len(block_spo2_packets) >= target_records:
                    break
                if now - page_start > 2.0:
                    break

                events = self.read_packets(base_timestamp, debug=debug)
                if events:
                    for event in events:
                        if event.sequence_gap:
                            total_sequence_gaps += 1
                        if event.packet_type == "FLASH_SENTINEL":
                            flash_sentinel_hit = True
                            break
                        if event.packet_type == "CORRUPT_FRAME":
                            corrupt_frames += 1
                            page_received_packets = True
                            last_packet_time = time.time()
                        if event.packet_type == "STORED_BLOCK":
                            page_received_packets = True
                            last_packet_time = time.time()
                            total_packets += 1
                            if event.spo2 is not None and event.heart_rate is not None:
                                flush_block_buffers()
                                is_po = "probe-out" in event.status_text or "searching" in event.status_text
                                session_records.append({
                                    "session_id": session_id,
                                    "user_id": session_info.user_id,
                                    "block_id": event.block_id,
                                    "sequence": event.sequence,
                                    "timestamp": (base_timestamp + timedelta(seconds=len(session_records))).isoformat(),
                                    "spo2": None if is_po else event.spo2,
                                    "heart_rate": None if is_po else event.heart_rate,
                                    "flags": event.status_text,
                                })
                            elif event.spo2 is not None:
                                block_spo2_packets.append(event)
                            elif event.heart_rate is not None:
                                block_heart_rate_packets.append(event)
                            elif event.invalid_sample:
                                (block_spo2_packets if event.block_id % 2 == 1 else block_heart_rate_packets).append(event)
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
            if not self._is_mock or (len(session_records) < target_records and not block_spo2_packets):
                pulse_command = Commands.session_page(2, session_id, page_index, session_info.user_id)
                if int(debug) >= 1:
                    print(f"[DEBUG OUT] Serial Engine Pulse Page #{page_index}: {pulse_command[:16].hex()}")
                self._write_report(pulse_command, f"Request Pulse Page #{page_index}")
                self._sleep(0.05)

                page_start = time.time()
                last_packet_time = time.time()
                pulse_received = False
                retries = 0

                while True:
                    now = time.time()
                    if not pulse_received and (now - page_start > 0.35):
                        if retries < 2 and not self._is_mock:
                            retries += 1
                            page_start = now
                            if int(debug) >= 1:
                                print(f"[DEBUG OUT] Retrying Pulse Page #{page_index} (attempt {retries+1})")
                            self._write_report(pulse_command, f"Retry Pulse Page #{page_index}")
                        else:
                            break
                    if pulse_received and (now - last_packet_time > 0.25):
                        break
                    if len(session_records) >= target_records or len(block_heart_rate_packets) >= target_records:
                        break
                    if now - page_start > 2.0:
                        break

                    events = self.read_packets(base_timestamp, debug=debug)
                    if events:
                        for event in events:
                            if event.sequence_gap:
                                total_sequence_gaps += 1
                            if event.packet_type == "FLASH_SENTINEL":
                                flash_sentinel_hit = True
                                break
                            if event.packet_type == "CORRUPT_FRAME":
                                corrupt_frames += 1
                                pulse_received = True
                                page_received_packets = True
                                last_packet_time = time.time()
                            if event.packet_type == "STORED_BLOCK":
                                pulse_received = True
                                page_received_packets = True
                                last_packet_time = time.time()
                                total_packets += 1
                                if event.spo2 is not None and event.heart_rate is not None:
                                    flush_block_buffers()
                                    is_po = "probe-out" in event.status_text or "searching" in event.status_text
                                    session_records.append({
                                        "session_id": session_id,
                                        "user_id": session_info.user_id,
                                        "block_id": event.block_id,
                                        "sequence": event.sequence,
                                        "timestamp": (base_timestamp + timedelta(seconds=len(session_records))).isoformat(),
                                        "spo2": None if is_po else event.spo2,
                                        "heart_rate": None if is_po else event.heart_rate,
                                        "flags": event.status_text,
                                    })
                                elif event.heart_rate is not None:
                                    block_heart_rate_packets.append(event)
                                elif event.spo2 is not None:
                                    block_spo2_packets.append(event)
                                elif event.invalid_sample:
                                    (block_spo2_packets if event.block_id % 2 == 1 else block_heart_rate_packets).append(event)
                    if flash_sentinel_hit:
                        break
                    if not events:
                        # T-084: see the matching comment in the SpO2 page loop above.
                        self._sleep(IDLE_READ_SLEEP)

            flush_block_buffers()

            if not int(debug) >= 1 and page_received_packets:
                print(f"\r[Serial Engine] Downloaded {total_packets} pkts for Session #{session_id} ({len(session_records)}/{target_records} records)...", end="", flush=True)

            if flash_sentinel_hit or not page_received_packets or len(session_records) >= target_records:
                break
            if len(session_records) == records_before:
                break

        flush_block_buffers()

        # Step 3: Non-destructive segment acknowledgment (0x9D 0x02 0x7F 0x7F 0x7F 0x00 0x00 0x00 0x1C)
        ack_command = Commands.segment_ack()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Non-Destructive Segment Ack (0x9D 0x02): {ack_command[:16].hex()}")
        self._write_report(ack_command, "Segment Ack (0x9D 0x02)")
        self._sleep(0.05)

        print(f"\nSession #{session_id} download complete ({len(session_records)} records, {total_packets} packets, {total_sequence_gaps} sequence gaps).")
        if corrupt_frames:
            print(f"WARNING: {corrupt_frames} stored frame(s) failed their checksum and were dropped; "
                  f"Session #{session_id} is missing those samples and its SpO2 and pulse values may be misaligned "
                  f"from that point on. Download it again.")
        return session_records

    def read_device_info(self, debug: Union[bool, int] = 0) -> Dict[str, Any]:
        """Queries and returns device hardware, firmware, RTC clock, user profile, and geometry info."""
        info = DeviceInfo()
        active_user_id = 1
        rtc_time_text = "N/A"

        # Step 1: Send Unlock Handshake & Storage Negotiation (0xA7 + 0xA2)
        self.device.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        negotiate_reply = self._dequeue_report()
        if negotiate_reply:
            active_user_id = Parsers.parse_user_id(negotiate_reply)

        # Step 2: Query RTC Clock (0x82)
        self.device.write_report(Commands.read_time())
        time.sleep(0.15)
        events = self.read_packets(debug=debug)
        if any(event.packet_type == "RTC_RESPONSE" for event in events):
            rtc_time_text = CLOCK_NOT_REPORTED

        # Step 3: Query Info (0xAD)
        self.device.write_report(Commands.build_hid(0xAD))
        time.sleep(0.15)
        report = self._dequeue_report()
        if report:
            parsed_info = Parsers.parse_device_info(report)
            if parsed_info.firmware_version:
                info.firmware_version = parsed_info.firmware_version
            if parsed_info.serial_number:
                info.serial_number = parsed_info.serial_number

        # Step 4: Query 0x81 (Firmware Version Query)
        self.device.write_report(Commands.build_hid(0x81, [0x01]))
        time.sleep(0.1)
        firmware_report = self._dequeue_report()
        if firmware_report and firmware_report[0] == 0x81:
            firmware_info = Parsers.parse_device_info(firmware_report)
            if firmware_info.firmware_version:
                info.firmware_version = firmware_info.firmware_version
        elif firmware_report and firmware_report[0] == 0xF1:
            # The real device answers 0x81 with the hardware model descriptor (e.g. "50F"), not a firmware version.
            # 8 model bytes only (PROTOCOL.md 0xF1 reply: `F1` + 8 bytes + checksum) -- [1:10] used to
            # include the checksum byte too, invisible with "50F" (its checksum filters out as non-alnum)
            # but leaking an extra alnum character for other model strings (found via the serial emulator).
            model = firmware_report[1:9].decode("ascii", errors="ignore").strip()
            info.hardware_id = "".join(char for char in model if char.isalnum() or char in "-_ ").strip() or None

        # Step 5: Query 0x8E (Serial Number / User Profile Query)
        # T-089: NOT migrated to wait_for_packet(). The detector's SERIAL_PROFILE branch only
        # fires on buf[0] == 0x8E (detector.py ~line 291), but the real reply's first byte is
        # 0xF1 or 0xFE -- which the DEVICE_INFO branch above it (buf[0] in [0x81, 0xFE, 0xF1,
        # 0xF0], ~line 276) catches first and parses with parse_device_info(), which never
        # extracts user_profile. So the 16-byte detector path cannot reach parse_serial() for
        # this reply at all; the two paths are not equivalent. Confirmed by a real test
        # regression (lost User Profile String) when this was tried. Stays a direct read.
        self.device.write_report(Commands.build_hid(0x8E, [0x03, 0x11]))
        time.sleep(0.1)
        for _ in range(3):
            serial_report = self._dequeue_report()
            if serial_report:
                serial_number, user_profile = Parsers.parse_serial(serial_report)
                if serial_number:
                    info.serial_number = serial_number
                if user_profile:
                    info.user_profile = user_profile
            time.sleep(0.05)

        # Step 6: Query 0x9E (Extended Storage Architecture Query)
        # T-089: migrated onto wait_for_packet() -- Parsers.parse_geometry() only ever reads
        # offsets 0..2, so the detector's 16-byte GEOMETRY_INFO chunk and the old 64-byte
        # direct parse are equivalent. A/B-tested against real hardware: both report "not
        # reported by the device" for this field (pre-existing, not a migration regression).
        self.device.write_report(Commands.build_hid(0x9E, [0x40, 0x04]))
        geometry_event = self.wait_for_packet("GEOMETRY_INFO", timeout=0.1, debug=debug)
        if geometry_event and geometry_event.device_info and geometry_event.device_info.flash_geometry:
            info.flash_geometry = geometry_event.device_info.flash_geometry

        return {
            "device_info": info,
            "active_user_id": active_user_id,
            "rtc_time_text": rtc_time_text,
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
        self.device.write_report(Commands.unlock_handshake())
        time.sleep(0.15)
        self._flush_before_command(debug=debug)  # Flush ACK

        self.device.write_report(Commands.reset_session_index())
        time.sleep(0.08)
        self._flush_before_command(debug=debug)  # Flush ACK

        session_map = {}
        # T-087: this upper bound is a safety net against a runaway loop, not a real limit on
        # how many sessions a device can hold -- actual termination is the 0x40 terminator bit
        # below, or SLOT_READ_ATTEMPTS misses in a row (a device with no more sessions to report).
        for slot in range(1, MAX_SESSION_SLOTS + 1):
            self.device.write_report(Commands.query_sessions())
            # SLOT_READ_ATTEMPTS misses in a row at 0.05s apiece -- same total budget as before
            # this used wait_for_packet(), just polled more finely instead of in 3 fixed steps.
            ec_event = self.wait_for_packet("SESSION_INDEX", timeout=SLOT_READ_ATTEMPTS * 0.05, debug=debug)

            if not ec_event or not ec_event.session_info:
                break

            session = ec_event.session_info
            if session.record_count > 0 or session.timestamp:
                session_map[session.session_id] = session

            if ec_event.raw_payload and len(ec_event.raw_payload) > 1 and (ec_event.raw_payload[1] & 0x40):
                break

        sessions = sorted(list(session_map.values()), key=lambda entry: entry.session_id)
        if not sessions:
            # A device in Manual recording mode lists nothing here; its one recording has its own
            # header query (PROTOCOL.md 3.14, T-042). Asked only when the Auto list is empty.
            header = self.read_manual_header(debug=debug)
            if header is not None and header.samples > 0:
                sessions.append(SessionInfo(session_id=1, user_id=1, record_count=header.samples,
                                            stored_duration_seconds=header.samples, timestamp=header.start,
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
        got = self._manual_frames(lambda frames: any(frame[0] == manual.HEADER for frame in frames), timeout=0.5, debug=debug)
        header = next((manual.parse_header(frame) for frame in got if frame[0] == manual.HEADER), None)
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
                lambda frames: len(values) + manual.SAMPLES_PER_SUBFRAME * sum(frame[0] == reply for frame in frames) >= samples,
                timeout=2.0, debug=debug)
            progressed = False
            for frame in (frame for frame in got if frame[0] == reply):
                expected = len(values) // manual.SAMPLES_PER_SUBFRAME
                sequence = manual.subframe_sequence(frame)
                if sequence == expected:
                    values.extend(manual.decode_subframe(frame))
                    progressed = True
                elif sequence > expected and sequence not in pending:
                    pending[sequence] = manual.decode_subframe(frame)
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

    def download_manual(self, session_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """Downloads the Manual-mode recording: SpO2 (`A3`), ack (`A7 01`), pulse (`A2`), ack (`A7 00`),
        then `A3 7F` / `A2 7F` to end. Read-only: nothing here erases the recording."""
        samples = session_info.record_count
        base_timestamp = session_info.timestamp or datetime.now()
        self._flush_before_command(debug=debug)
        self._write_report(bytes([0x80]) + bytes(63), "Stop live stream (0x80)")
        self._manual_frames(lambda frames: False, timeout=0.1, quiet=0.05)

        spo2 = self._manual_series(manual.SPO2_REQUEST, manual.SPO2_DATA, samples, debug=debug)
        self._write_report(manual.block_ack(True), "Manual SpO2 done (0xA7 01)")
        self._manual_frames(lambda frames: any(frame[0] == manual.BLOCK_ACK for frame in frames), timeout=0.3)
        pulse = self._manual_series(manual.PULSE_REQUEST, manual.PULSE_DATA, samples, debug=debug)
        self._write_report(manual.block_ack(False), "Manual pulse done (0xA7 00)")
        self._manual_frames(lambda frames: any(frame[0] == manual.BLOCK_ACK for frame in frames), timeout=0.3)
        self._write_report(manual.series_end(manual.SPO2_REQUEST), "Manual end (0xA3 7F)")
        self._write_report(manual.series_end(manual.PULSE_REQUEST), "Manual end (0xA2 7F)")

        out = []
        for i, (spo2_value, pulse_value) in enumerate(manual.records(spo2, pulse, samples)):
            out.append({
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "block_id": 1,
                "sequence": i // manual.SAMPLES_PER_SUBFRAME,
                "timestamp": (base_timestamp + timedelta(seconds=i)).isoformat(),
                "spo2": spo2_value,
                "heart_rate": pulse_value,
                "flags": "ok" if spo2_value is not None else "probe-out",
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
            self.dump_file = open(dump_file, "w", encoding="utf-8")
            self.last_dump_time = time.time()
            self.dump_file.write("# Pulsox PO-400 Session Download HID Frame Trace Dump\n")
            self.dump_file.write(f"# Generated: {datetime.now().isoformat()}\n\n")

        try:
            session_list = self.list_sessions(debug=debug)

            if not download_all and target_session > 0:
                matched = [session for session in session_list if session.session_id == target_session]
                if matched:
                    session_list = matched
                else:
                    print(f"Target Session #{target_session} not found in index table; using default bounds...")
                    session_list = [SessionInfo(session_id=target_session, user_id=1, record_count=60, stored_duration_seconds=60)]

            if not session_list:
                print("No active session table returned; defaulting to downloading Session #1...")
                session_list = [SessionInfo(session_id=1, user_id=1, record_count=60, stored_duration_seconds=60)]

            session_ids = [session.session_id for session in session_list]
            print(f"Found {len(session_list)} session(s) to download: {session_ids}")

            total_records = []
            for session_info in session_list:
                session_id = session_info.session_id
                duration_text = session_info.duration_text
                print(f"\n---> Requesting Session #{session_id} Data Blocks ({duration_text})...")

                if timeout_override > 0:
                    # -t/--timeout caps the download at that many seconds (= records, 1 per second).
                    timeout_cap = int(timeout_override)
                    session_info.stored_duration_seconds = min(session_info.stored_duration_seconds, timeout_cap) if session_info.stored_duration_seconds > 0 else timeout_cap
                    if session_info.record_count > 0:
                        session_info.record_count = min(session_info.record_count, timeout_cap)

                records = self.download_session(session_info, debug=debug)
                total_records.extend(records)

            print(f"\nDownload complete. Total records collected across all sessions: {len(total_records)}")
            return total_records
        finally:
            if self.dump_file:
                self.dump_file.close()
                self.dump_file = None

    def read_rtc_time(self, debug: Union[bool, int] = 0) -> Optional[bytes]:
        """Sends the clock query and returns the raw 0xF2 reply, or None if none came.

        The reply has been the same 8 bytes in every recording (PROTOCOL.md §3.3), so it
        is returned as is rather than decoded into a time.
        """
        read_command = Commands.read_time()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Read RTC: {read_command[:16].hex()}")
        self.device.write_report(read_command)
        rtc_event = self.wait_for_packet("RTC_RESPONSE", timeout=0.15, debug=debug)
        return rtc_event.raw_payload if rtc_event else None

    def set_rtc_time(self, target_date_time: Optional[datetime] = None, debug: Union[bool, int] = 0) -> bool:
        """Sets device RTC timestamp."""
        unlock_command = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {unlock_command[:16].hex()}")
        self.device.write_report(unlock_command)
        time.sleep(0.15)
        self._flush_before_command(debug=debug)  # Flush ACK

        set_command = Commands.set_time(target_date_time)
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Set RTC: {set_command[:16].hex()}")
        self.device.write_report(set_command)
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
        unlock_command = Commands.unlock_handshake()
        if int(debug) >= 1:
            print(f"[DEBUG OUT] Serial Engine Unlock Handshake: {unlock_command[:16].hex()}")
        self.device.write_report(unlock_command)
        time.sleep(0.2)
        report = self._dequeue_report()
        if report:
            if int(debug) >= 1:
                print(f"[DEBUG IN] Handshake Response: {report[:16].hex()}")
            return Parsers.parse_user_id(report)
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
        manual_target = next((session for session in before if session.manual and (session_id <= 0 or session.session_id == session_id)), None)
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
        targets = [session for session in before if not session.manual and (session_id <= 0 or session.session_id == session_id)]
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
            return not any(not session.manual and session.session_id == session_id for session in after)
        gone = {(target.user_id, target.session_id) for target in targets}
        left = [session for session in after if not session.manual and (session.user_id, session.session_id) in gone]
        if session_id > 0:
            # Entries are renumbered after a delete; compare start times, not numbers.
            left = [session for session in after if not session.manual and session.timestamp == targets[0].timestamp]
        return not left

    def _clear_auto_all(self, debug: Union[bool, int] = 0) -> None:
        """Sends the "erase all" step (`9D 7F`) and waits for its erase-reply status. Just the
        one step -- verification (did it actually disappear) happens back in `_clear_auto()`."""
        command, description = Commands.delete_all(), "Delete All (0x9D 0x7F)"
        if int(debug) >= 1:
            print(f"[DEBUG OUT] {description}: {command[:16].hex()}")
        self._write_report(command, description)
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
        for step_number, (command, description) in enumerate(steps):
            if int(debug) >= 1:
                print(f"[DEBUG OUT] {description}: {command[:16].hex()}")
            self._write_report(command, description)
            self._sleep(0.5)
            status = self._erase_status()
            if int(debug) >= 1:
                print(f"[DEBUG] Erase reply status: {'none' if status is None else status}")
            if status not in (None, 0):
                break
            if status is None and step_number == 0:
                self.single_erase_unsupported = True
                break

    def _clear_manual(self, debug: Union[bool, int] = 0) -> bool:
        """Erases the Manual-mode recording with SpO2.exe's own, unconfirmed `A1`/`D1` sequence
        (PROTOCOL.md 3.14 G, T-072): `A1 00`, then `A1 01` once the device confirms the first.
        `A1 04` (third series) is not sent -- Manual mode has no known way to tell whether it
        applies. Verified the same way as the Auto-mode path: by listing again afterwards.
        """
        for step in (0, 1):
            description = f"Manual delete step 0x{step:02X} (0xA1)"
            if int(debug) >= 1:
                print(f"[DEBUG OUT] {description}: {manual.delete_step(step)[:16].hex()}")
            status = self._manual_delete_step(step, debug=debug)
            if int(debug) >= 1:
                print(f"[DEBUG] Erase reply status: {'none' if status is None else status}")
            if status not in (None, 0):
                break

        after = self.list_sessions(debug=debug)
        return not any(session.manual for session in after)

    def _manual_delete_step(self, step: int, debug: Union[bool, int] = 0) -> Optional[int]:
        """Sends one Manual-mode erase step (`A1`) and returns its `D1` reply's status byte
        (0 = done), or None if no reply came."""
        self._flush_before_command(debug=debug)
        self._write_report(manual.delete_step(step), f"Manual delete step 0x{step:02X} (0xA1)")
        got = self._manual_frames(lambda frames: any(frame[0] == manual.DELETE_REPLY for frame in frames), timeout=1.0, debug=debug)
        reply = next((frame for frame in got if frame[0] == manual.DELETE_REPLY), None)
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
            raw_report = self._dequeue_report()
            if not raw_report:
                self._sleep(IDLE_READ_SLEEP)
                continue
            last = time.time()
            report = bytes(raw_report)
            i = report.find(b"\xed\x7f")
            if i >= 0 and i + 7 <= len(report) and (sum(report[i:i + 6]) & 0x7F) == report[i + 6]:
                status = report[i + 5]
        return status
