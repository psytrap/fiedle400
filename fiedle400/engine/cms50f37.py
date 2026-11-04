"""Read-only engine for the PO-250 in protocol B (T-105, PROTOCOL_B.md).

It offers the parts of `SerialDeviceEngine`'s interface the CLI uses for `info`, `sessions`
and `download`. Everything that writes to the device (erase, clock) or streams live data is
refused here and never sent: fiedle400 only downloads from the PO-250 (T-061). `AE` (erase)
and `AA` (the PO-400's `FLASH_CLEAR`) are not even in `protocol.cms50f37`.

Built from Contec's protocol spec V7.0, OSCAR's `cms50f37_loader.cpp` and kaivol/pulox (written
against a PO-250), and replayed against a real CMS50F 3.7 download by SpO2 Assistant
(tests/fixtures/cms50f37-download.trace.json). Untested on a real PO-250 (T-105).
"""

import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..protocol import DeviceInfo, SessionInfo
from ..protocol import cms50f37 as protocol_b

REPLY_TIMEOUT = 1.0    # OSCAR waits up to 2 s; the capture answers within about 30 ms
QUIET_END = 2.0        # the device just stops sending at the end of a recording (OSCAR: 2 s)
PROGRESS_EVERY = 3600  # samples between progress lines (one hour of recording)

Frames = List[protocol_b.Frame]


class Cms50F37Engine:
    """Protocol-B counterpart of `SerialDeviceEngine` (download only)."""

    protocol = "cms50f37"

    def __init__(self, device, background_reader: bool = False):
        self.device = device
        model = getattr(device, "model_string", None)
        self.model: Optional[str] = model if isinstance(model, str) else None
        self.single_erase_unsupported = False
        self.download_warnings: List[str] = []
        self._rest = b""
        self._sleep = time.sleep
        self._clock = time.time

    def close(self):
        pass

    # --- transport -------------------------------------------------------------------------
    def _send(self, opcode: int, session: int = 0, debug: Union[bool, int] = 0) -> None:
        command = protocol_b.build_command(opcode, session=session)
        if int(debug) >= 1:
            print(f"[DEBUG OUT] protocol B: {command.hex(' ')}")
        self.device.write_raw(command)

    def _read_frames(self, done: Callable[[Frames], bool], timeout: float = REPLY_TIMEOUT,
                     debug: Union[bool, int] = 0) -> Frames:
        """Reads frames until `done(frames)` or `timeout` seconds without a new byte."""
        frames: Frames = []
        last = self._clock()
        while not done(frames):
            report = self.device.read_report(64)
            if report:
                last = self._clock()
                if int(debug) >= 2:
                    print(f"[DEBUG IN] protocol B: {bytes(report).hex(' ')}")
                got, self._rest = protocol_b.split_frames(self._rest + bytes(report), strict=True)
                frames.extend(got)
            elif self._clock() - last >= timeout:
                break
            else:
                self._sleep(0.005)
        return frames

    def _ask(self, opcode: int, want: int, session: int = 0, count: int = 1,
             debug: Union[bool, int] = 0) -> Frames:
        self._send(opcode, session=session, debug=debug)
        return self._read_frames(lambda frames: sum(1 for frame in frames if frame.code == want) >= count,
                                 debug=debug)

    def _hello(self, debug: Union[bool, int] = 0) -> None:
        """`A7` then `A2`: stops any stream, as OSCAR, kaivol and SpO2 Assistant do first."""
        self._rest = b""
        self._ask(protocol_b.HELLO1, protocol_b.REPLY_HELLO, debug=debug)
        self._ask(protocol_b.HELLO2, protocol_b.REPLY_HELLO, debug=debug)

    # --- queries ---------------------------------------------------------------------------
    def read_raw_report(self, timeout: float = 0.0) -> Optional[bytes]:
        return self.device.read_report(64)

    def unlock_handshake(self, debug: Union[bool, int] = 0) -> int:
        """Protocol B's hello; returns the user number (1: the PO-250 has one user)."""
        self._hello(debug=debug)
        return 1

    def read_model(self, debug: Union[bool, int] = 0) -> Optional[str]:
        if self.model is None:
            frames = self._ask(protocol_b.MODEL, protocol_b.REPLY_MODEL, count=2, debug=debug)
            self.model = protocol_b.model_from_frames(frames)
        return self.model

    def read_device_info(self, debug: Union[bool, int] = 0) -> Dict[str, Any]:
        self._hello(debug=debug)
        info = DeviceInfo()
        info.hardware_id = self.read_model(debug=debug)
        counted = protocol_b.session_count(self._ask(protocol_b.SESSION_COUNT, protocol_b.REPLY_COUNT, debug=debug))
        return {
            "device_info": info,
            "active_user_id": (counted[0] + 1) if counted else 1,
            "rtc_time_text": "not read (protocol B)",
        }

    def list_sessions(self, debug: Union[bool, int] = 0, attempts: int = 2, retry_delay: float = 0.3) -> List[SessionInfo]:
        for attempt in range(attempts):
            sessions = self._list_sessions_once(debug=debug)
            if sessions or attempt == attempts - 1:
                return sessions
            self._sleep(retry_delay)
        return []

    def _list_sessions_once(self, debug: Union[bool, int] = 0) -> List[SessionInfo]:
        """`A3` (how many recordings), then `A4` (length) and `A5` (start) for each one."""
        self._hello(debug=debug)
        counted = protocol_b.session_count(self._ask(protocol_b.SESSION_COUNT, protocol_b.REPLY_COUNT, debug=debug))
        if not counted:
            return []
        user, count = counted
        sessions = []
        for index in range(count):
            length = protocol_b.session_length(
                self._ask(protocol_b.SESSION_LENGTH, protocol_b.REPLY_LENGTH, session=index, debug=debug))
            start = protocol_b.session_start(
                self._ask(protocol_b.SESSION_TIME, protocol_b.REPLY_TIME, session=index, debug=debug))
            samples = (length or 0) // protocol_b.BYTES_PER_SAMPLE
            sessions.append(SessionInfo(session_id=index + 1, user_id=user + 1, record_count=samples,
                                        stored_duration_seconds=samples, raw_samples=samples,
                                        timestamp=start.as_datetime() if start else None))
        return sessions

    # --- download --------------------------------------------------------------------------
    def download_session(self, session_info: SessionInfo, debug: Union[bool, int] = 0) -> List[Dict[str, Any]]:
        """`A7`, `A2`, then `A6 [session]`; the device streams data frames and goes quiet at the end."""
        expected = session_info.record_count
        base_timestamp = session_info.timestamp or datetime.now()
        self._hello(debug=debug)
        self._send(protocol_b.SESSION_DATA, session=session_info.session_id - 1, debug=debug)

        pairs: List[Tuple[Optional[int], Optional[int]]] = []
        next_note = PROGRESS_EVERY

        def done(frames: Frames) -> bool:
            nonlocal next_note
            while frames:
                pairs.extend(protocol_b.samples(frames.pop(0)))
            if len(pairs) >= next_note:
                print(f"  ... {len(pairs):,} of {expected:,} samples")
                next_note += PROGRESS_EVERY
            return expected > 0 and len(pairs) >= expected

        self._read_frames(done, timeout=QUIET_END, debug=debug)
        if expected > 0 and len(pairs) >= expected:
            pairs = pairs[:expected]
        self._send(protocol_b.HELLO1, debug=debug)  # stop a stream that may still be running

        records = []
        for index, (spo2, pulse) in enumerate(pairs):
            records.append({
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "block_id": 1,
                "sequence": index,
                "timestamp": (base_timestamp + timedelta(seconds=index)).isoformat(),
                "spo2": spo2,
                "heart_rate": pulse,
                "flags": "ok" if spo2 is not None else "probe-out",
            })
        print(f"\nSession #{session_info.session_id} download complete ({len(records)} records).")
        if expected and len(records) < expected:
            warning = (f"the device sent {len(records):,} of the {expected:,} samples it announced for "
                       f"recording #{session_info.session_id}; the rest is missing. Download it again.")
            print(f"WARNING: {warning}")
            self.download_warnings.append(warning)
        return records

    def download_all_sessions(self, target_session: int = 0, download_all: bool = True,
                              timeout_override: float = 0, debug: Union[bool, int] = 0,
                              dump_file: Optional[str] = None) -> List[Dict[str, Any]]:
        if dump_file:
            print("Note: --dump is not supported for the PO-250 (protocol B); use -vv to see the traffic.")
        sessions = self.list_sessions(debug=debug)
        if not download_all and target_session > 0:
            sessions = [session for session in sessions if session.session_id == target_session]
            if not sessions:
                print(f"Recording #{target_session} is not on the device.")
                return []
        if not sessions:
            print("No recordings on the device.")
            return []
        print(f"Found {len(sessions)} session(s) to download: {[session.session_id for session in sessions]}")
        records: List[Dict[str, Any]] = []
        for session_info in sessions:
            if timeout_override > 0:
                cap = int(timeout_override)
                session_info.record_count = min(session_info.record_count, cap) if session_info.record_count else cap
                session_info.stored_duration_seconds = session_info.record_count
            print(f"\n---> Requesting Session #{session_info.session_id} ({session_info.duration_text})...")
            records.extend(self.download_session(session_info, debug=debug))
        return records

    # --- refused ---------------------------------------------------------------------------
    def read_packets(self, base_timestamp=None, debug: Union[bool, int] = 0) -> list:
        return []  # live mode is out of scope (T-061)

    def read_rtc_time(self, debug: Union[bool, int] = 0) -> Optional[bytes]:
        return None

    def set_rtc_time(self, target_date_time=None, debug: Union[bool, int] = 0) -> bool:
        print("Setting the clock is not supported for the PO-250 (protocol B).")
        return False

    def clear_memory(self, session_id: int = 0, debug: Union[bool, int] = 0) -> bool:
        """Never erases: the PO-250 is download-only in fiedle400 (`AE` is never sent)."""
        print("Erase is not supported for the PO-250; erase recordings on the device itself.")
        return False
