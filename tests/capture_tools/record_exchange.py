#!/usr/bin/env python3
"""Record the CLI's real traffic with a PO-400 into a replayable trace (read-only).

Runs the same read-only engine calls the CLI uses for ``info``, ``sessions`` and
``download`` and logs every report written to the device and every report read
back, grouped by command. The result (``tests/hwsim.py`` ``Trace`` JSON, format 1)
lets the simulated oximeter answer the CLI's own commands with real device bytes.

Safety: commands are checked before they are written. Anything that erases data
(``9D 7F ...``, the vendor's delete that ``clear`` sends, and the old candidates
0xAA/0xAB/0xAC, 0x91..0x96) raises instead of being sent, and
this script never calls ``clear_memory`` or ``set_rtc_time`` in the first place.
The download ends with the same non-destructive segment ack the CLI always sends.

The trace contains the recorded oximetry values and the device's clock, serial and
user name. Review it before sharing; ``--no-download`` records only ``info`` and
``sessions`` and holds no measurements.

Usage:
    python3 tests/capture_tools/record_exchange.py -o handoff/cli-exchange.trace.json
    python3 tests/capture_tools/record_exchange.py --no-download -o info-only.trace.json
    python3 tests/capture_tools/record_exchange.py --no-download --probe-firmware --probe-offsets 0,1,2,50,107,214,215,300 -o probe.trace.json

The two probes ask questions the normal flows never ask, to settle open findings (RELEASE_PLAN.md 3d):
``--probe-firmware`` sends the documented firmware query ``80 00`` (read-only); ``--probe-offsets``
requests SpO2 reads at the given sample offsets (the page number of a ``9D 04`` read is a sample
offset, T6), so a session longer than one reply shows what offset unit the device uses and what it
sends once the offset is past the end of the data (silence, a short reply, an end marker).
"""

import argparse
import os
import sys
import time
from typing import List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from hwsim import Trace, command_key  # noqa: E402
from fiedle400.protocol import Commands  # noqa: E402
from fiedle400.engine import SerialDeviceEngine  # noqa: E402
from fiedle400.hid_driver import PulsoxHidDevice  # noqa: E402


class RefusedCommand(RuntimeError):
    """A destructive command was about to be written; nothing was sent."""


class RecordingDevice:
    """Wraps a connected device: logs traffic per command and refuses destructive writes."""

    def __init__(self, dev):
        self._dev = dev
        self.exchanges: List[list] = []  # [out_report, [in_reports]]

    def write_report(self, data: bytes) -> int:
        key = command_key(data)
        if key is not None and key[0] == "destructive":
            raise RefusedCommand(f"refusing to send a destructive command: {bytes(data)[:12].hex()}")
        self.exchanges.append([bytes(data), []])
        return self._dev.write_report(data)

    def read_report(self, max_bytes: int = 64) -> Optional[bytes]:
        rep = self._dev.read_report(max_bytes)
        if rep and self.exchanges:
            self.exchanges[-1][1].append(bytes(rep))
        return rep

    def __getattr__(self, name):  # connect/close/backend_name/...; AttributeError for 'responses' keeps the engine in real-device mode
        return getattr(self._dev, name)

    def to_trace(self, source: str) -> Trace:
        t = Trace(source=source)
        for out, ins in self.exchanges:
            t.add(out, ins)
        return t


def _drain(rec, first_timeout: float = 0.35, quiet: float = 0.25, clock=time) -> int:
    """Read until the device has answered and then gone quiet; return the number of reports."""
    start = last = clock.time()
    n = 0
    while True:
        now = clock.time()
        if n == 0 and now - start > first_timeout:
            return 0
        if n and now - last > quiet:
            return n
        if rec.read_report(64):
            n += 1
            last = clock.time()
        else:
            clock.sleep(0.005)


def probe_firmware(rec, clock=time) -> None:
    """The documented firmware query (80 00). Read-only."""
    while rec.read_report(64):
        pass
    rec.write_report(Commands.build_hid(0x80, [0x00]))
    _drain(rec, clock=clock)


def probe_offsets(rec, session_id: int, user_id: int, offsets: List[int], clock=time) -> None:
    """SpO2 reads at the given sample offsets, as the download does for pages 0, 1, 2 (read-only)."""
    while rec.read_report(64):
        pass
    rec.write_report(Commands.unlock_handshake())
    clock.sleep(0.05)
    rec.write_report(Commands.storage_init())
    clock.sleep(0.05)
    while rec.read_report(64):
        pass
    for off in offsets:
        rec.write_report(Commands.session_page(1, session_id, off, user_id))
        clock.sleep(0.05)
        _drain(rec, clock=clock)
    rec.write_report(Commands.segment_ack())   # the same non-destructive ack the download ends with
    clock.sleep(0.05)
    _drain(rec, clock=clock)


def parse_offsets(text: str) -> List[int]:
    out = [int(x) for x in text.split(",") if x.strip()]
    if not out or any(not 0 <= o < 1 << 14 for o in out):
        raise ValueError("offsets are comma separated integers in 0..16383")
    return out


def record(dev, download: bool = True, session: int = 0, offsets: Optional[List[int]] = None,
           firmware: bool = False, clock=time) -> Trace:
    """Run the read-only flows on a connected device and return what was exchanged."""
    rec = RecordingDevice(dev)
    engine = SerialDeviceEngine(rec)
    engine.read_device_info()
    sessions = engine.list_sessions()
    if download:
        for s in sessions:
            if session and s.session_id != session:
                continue
            engine.download_session(s)
    if firmware:
        probe_firmware(rec, clock=clock)
    if offsets and sessions:
        target = next((s for s in sessions if s.session_id == session), sessions[0])
        probe_offsets(rec, target.session_id, target.user_id, offsets, clock=clock)
    return rec.to_trace(source=f"record_exchange.py on {getattr(dev, 'backend_name', '?')} backend")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", required=True, help="Trace file to write (JSON).")
    ap.add_argument("--backend", choices=["hidraw", "hid"], help="HID backend (default: platform default).")
    ap.add_argument("-d", "--device", help="Device node path (optional).")
    ap.add_argument("--no-download", action="store_true", help="Record info and sessions only (no measurements).")
    ap.add_argument("--session", type=int, default=0, help="Download only this session id (default: all).")
    ap.add_argument("--probe-offsets", metavar="N,N,...", help="Also request SpO2 reads at these sample offsets (read-only).")
    ap.add_argument("--probe-firmware", action="store_true", help="Also send the documented firmware query 80 00 (read-only).")
    args = ap.parse_args(argv)
    offsets = parse_offsets(args.probe_offsets) if args.probe_offsets else None

    dev = PulsoxHidDevice(dev_path=args.device, backend=args.backend)
    print(f"Connected to {dev.connect()}")
    try:
        trace = record(dev, download=not args.no_download, session=args.session,
                       offsets=offsets, firmware=args.probe_firmware)
    finally:
        dev.close()
    trace.to_json(args.output, note="Recorded from a real device; contains device identifiers and, unless --no-download, measurements.")
    print(f"Recorded {len(trace.groups)} command exchanges to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
