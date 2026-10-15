#!/usr/bin/env python3
"""Record the CLI's real traffic with a PO-400 into a replayable trace (read-only).

Runs the same read-only engine calls the CLI uses for ``info``, ``sessions`` and
``download`` and logs every report written to the device and every report read
back, grouped by command. The result (``tests/hwsim.py`` ``Trace`` JSON, format 1)
lets the simulated oximeter answer the CLI's own commands with real device bytes.

Safety: commands are checked before they are written. Anything that erases data
(the ``clear`` family, 0xAA/0xAB/0xAC, 0x91..0x96) raises instead of being sent, and
this script never calls ``clear_memory`` or ``set_rtc_time`` in the first place.
The download ends with the same non-destructive segment ack the CLI always sends.

The trace contains the recorded oximetry values and the device's clock, serial and
user name. Review it before sharing; ``--no-download`` records only ``info`` and
``sessions`` and holds no measurements.

Usage:
    python3 tests/capture_tools/record_exchange.py -o handoff/cli-exchange.trace.json
    python3 tests/capture_tools/record_exchange.py --no-download -o info-only.trace.json
"""

import argparse
import os
import sys
from typing import List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from hwsim import Trace, command_key  # noqa: E402
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


def record(dev, download: bool = True, session: int = 0) -> Trace:
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
    return rec.to_trace(source=f"record_exchange.py on {getattr(dev, 'backend_name', '?')} backend")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", required=True, help="Trace file to write (JSON).")
    ap.add_argument("--backend", choices=["hidraw", "hid"], help="HID backend (default: platform default).")
    ap.add_argument("-d", "--device", help="Device node path (optional).")
    ap.add_argument("--no-download", action="store_true", help="Record info and sessions only (no measurements).")
    ap.add_argument("--session", type=int, default=0, help="Download only this session id (default: all).")
    args = ap.parse_args(argv)

    dev = PulsoxHidDevice(dev_path=args.device, backend=args.backend)
    print(f"Connected to {dev.connect()}")
    try:
        trace = record(dev, download=not args.no_download, session=args.session)
    finally:
        dev.close()
    trace.to_json(args.output, note="Recorded from a real device; contains device identifiers and, unless --no-download, measurements.")
    print(f"Recorded {len(trace.groups)} command exchanges to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
