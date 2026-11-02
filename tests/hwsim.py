"""Simulated PO-400 hardware for tests: a command-checking fake device and a Linux hidraw stand-in.

Two pieces, usable separately:

* ``FakeOximeter`` answers host commands by *replaying recorded device bytes*. It
  never invents a reply: a command it has no recording for is logged in
  ``unmatched`` and gets no answer, so the code under test sees a timeout, as it
  would on a device that ignored the command. It also logs every report the host
  sent (``sent``) so tests can assert on the bytes the code *sends*, and refuses
  to model any destructive opcode (``destructive`` records an attempt).

* ``HidrawSim`` makes the real ``LinuxHidrawBackend`` run against a FakeOximeter:
  a fake ``/sys/class/hidraw`` + ``/dev`` tree for ``find_pulsox_hid_devices()``,
  and a ``SOCK_SEQPACKET`` socket (message boundaries like a hidraw node, EAGAIN
  when empty) behind the file descriptor ``os.open`` returns. Replies are queued
  synchronously inside ``os.write``, so runs are deterministic. ``VirtualClock``
  replaces the engine's ``time`` so its 250 ms quiet periods cost nothing.

Where the recordings come from (``Trace``):

* ``Trace.from_pcap()`` -- the reference capture in ``analysis/``. It was made
  with the vendor tool, so it covers only the commands that tool sent: one
  session header, page 0 of the SpO2 and pulse series of session 1, the RTC, the
  user name and the live stream.
* ``Trace.from_json()`` -- a recording of the CLI's own traffic made on a real
  device with ``tests/capture_tools/record_exchange.py`` (read-only commands).
  ``tests/fixtures/cli-exchange.trace.json`` is such a recording (18 exchanges, a
  214-sample session); with it every command the CLI sends has a recorded answer.

``FakeOximeter(strict=True)`` makes "the last recording repeats" stop: a command asked
more often than it was recorded is logged as unmatched and gets no answer. Use it with a
complete recording, so a request the device never answered on the wire cannot be answered
with another request's data.

Commands are matched on their meaning, not their framing: a leading ``7D 81``
channel prefix, trailing padding (``0x80`` from the CLI, ``0x00`` from the vendor
tool) and checksum bytes are ignored, because the real device accepts both
dialects. Host checksums are *not* validated -- the device's behaviour there is
unverified and the CLI's ``9C 80 00`` reset does not carry the checksum the spec
lists, yet works on hardware.
"""

import collections
import errno
import json
import os
import shutil
import socket
import tempfile
from typing import Callable, List, Optional, Tuple
from unittest import mock


def scrub_environment():
    """Remove the developer's FIEDLE400_*/PO400_* settings for one test.

    Use inside a `mock.patch.dict(os.environ, {})` (or `addCleanup` of one) so
    they are restored afterwards. Without it a developer who exports
    FIEDLE400_DEBUG=1 gets failures that CI never sees.
    """
    for key in [k for k in os.environ if k.startswith(("FIEDLE400_", "PO400_"))]:
        del os.environ[key]

REPORT_LENGTH = 64

# Opcodes that might change stored data. The vendor's real deletes are 0x9D with mode 0x7F
# (handled in command_key; PROTOCOL.md 3.13, T-037) for Auto-mode recordings, and 0xA1 for the
# Manual-mode one (PROTOCOL.md 3.14 G, T-072); `clear` sends both. 0xAA, 0x91..0x96 and the old
# clear's 0xAB/0xAC stay here as untested candidates. The simulator models none of them: an
# attempt is recorded in FakeOximeter.destructive and gets no reply. 0x94 is also the
# read-only sector query (`94 14`), so it only counts as destructive in any other form.
DESTRUCTIVE_OPCODES = frozenset([0x91, 0x92, 0x93, 0x95, 0x96, 0xAA, 0xAB, 0xAC, 0xA1])

# How many bytes after the opcode identify a command (checksum bytes excluded).
# Anything else is "unknown" and is never answered.
_KEY_ARGS = {
    0x80: 0, 0x81: 0, 0x82: 0, 0x83: 0, 0x94: 0,   # the next byte is only a checksum / clock value
    0x8E: 1, 0x90: 1, 0x9B: 1, 0x9C: 1,            # sub-index / control byte
    0xAD: 0, 0xA5: 1, 0xA6: 0,                     # device info, session select / download
    0x8F: 2, 0x9E: 2, 0x9F: 2,
    0xA0: 1, 0xA2: 3, 0xA3: 3,                     # Manual mode: header, pulse / SpO2 series (mode, offset)
}


def command_key(report: bytes) -> Optional[Tuple]:
    """Reduce an outbound report to what the command *means*; None when unknown."""
    data = bytes(report)
    if len(data) > 2 and data[0] == 0x7D and data[1] == 0x81:
        data = data[2:]
    if not data:
        return None
    opcode = data[0]
    if opcode == 0xA7:
        # 7D 81 A7 80 ... is the CLI's unlock; A7 00 / A7 01 is the Manual-mode block ack.
        return ("unlock",) if len(data) < 2 or data[1] == 0x80 else (opcode, data[1])
    if opcode in DESTRUCTIVE_OPCODES or (opcode == 0x94 and len(data) > 1 and data[1] != 0x14):
        return ("destructive", opcode)
    if opcode == 0x9D:
        # Storage: init / ack carry only a mode (the vendor tool sends 8 bytes, the CLI 9);
        # a block read (mode 0x04) is identified by type, user, entry and the two offset bytes.
        # Mode 0x7F deletes recordings (PROTOCOL.md 3.13, T-037).
        if len(data) < 2:
            return None
        if data[1] == 0x7F:
            return ("destructive", opcode)
        return (opcode, data[1]) + (tuple(data[2:7]) if data[1] == 0x04 else ())
    if opcode not in _KEY_ARGS:
        return None
    size = _KEY_ARGS[opcode]
    return (opcode,) + tuple(data[1:1 + size])


class Trace:
    """Recorded exchanges: for each command key, the groups of reports the device sent back."""

    def __init__(self, source: str = ""):
        self.source = source
        self.groups: List[Tuple[bytes, Optional[Tuple], List[bytes]]] = []  # (raw out, key, [in reports])

    # -- building ---------------------------------------------------------
    def add(self, output: bytes, replies: List[bytes]) -> None:
        self.groups.append((bytes(output), command_key(output), [bytes(i) for i in replies]))

    @classmethod
    def from_pcap(cls, path: str) -> "Trace":
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_tools"))
        from decode_pcap import parse_pcap_file  # noqa: E402
        trace = cls(source=os.path.basename(path))
        current: Optional[Tuple[bytes, List[bytes]]] = None
        for endpoint, payload in parse_pcap_file(path):
            if len(payload) != REPORT_LENGTH:
                continue  # USB setup / descriptor traffic, not HID reports
            if endpoint == 0x01:
                if current:
                    trace.add(*current)
                current = (payload, [])
            elif endpoint == 0x81 and current is not None:
                current[1].append(payload)
        if current:
            trace.add(*current)
        return trace

    @classmethod
    def from_json(cls, path: str) -> "Trace":
        with open(path, "r", encoding="utf-8") as file:
            document = json.load(file)
        if document.get("format") != 1:
            raise ValueError(f"{path}: unsupported trace format {document.get('format')!r}")
        trace = cls(source=document.get("source", os.path.basename(path)))
        for group in document["exchanges"]:
            trace.add(bytes.fromhex(group["out"]), [bytes.fromhex(hex_text) for hex_text in group["in"]])
        return trace

    def to_json(self, path: str, note: str = "") -> None:
        document = {
            "format": 1,
            "source": self.source,
            "note": note,
            "exchanges": [{"out": sent.hex(), "in": [i.hex() for i in replies]} for sent, _, replies in self.groups],
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(document, file, indent=1)
            file.write("\n")

    def with_header_samples(self, raw_samples: int) -> "Trace":
        """A copy whose 0xEC session headers announce ``raw_samples`` samples (to model a
        longer session than the recording holds; the data replies are unchanged)."""
        packed = bytes([raw_samples & 0x7F, (raw_samples >> 7) & 0x7F, (raw_samples >> 14) & 0x7F,
                        (raw_samples >> 21) & 0x7F])
        trace = Trace(source=self.source + f" (header: {raw_samples} raw samples)")
        for output, _, replies in self.groups:
            trace.add(output, [i[:10] + packed + i[14:] if i[:1] == b"\xec" else i for i in replies])
        return trace

    # -- lookup -----------------------------------------------------------
    def responses(self, key: Tuple) -> List[List[bytes]]:
        return [replies for _, k, replies in self.groups if k == key]

    def keys(self) -> List[Tuple]:
        seen, output = set(), []
        for _, k, _ in self.groups:
            if k is not None and k not in seen:
                seen.add(k)
                output.append(k)
        return output


class FakeOximeter:
    """Protocol-aware fake: replays recorded replies, logs everything, invents nothing."""

    def __init__(self, trace: Trace, fault: Optional[Callable[[Tuple, int, bytes], Optional[bytes]]] = None,
                 strict: bool = False):
        self.trace = trace
        self.strict = strict            # True: a command asked more often than it was recorded is unanswered
        self.fault = fault              # (key, index in reply, report) -> replacement report, or None to drop it
        self.sent: List[bytes] = []     # every report the host wrote, unmodified
        self.unmatched: List[bytes] = []
        self.destructive: List[bytes] = []
        self.unplugged = False
        self._seen = collections.Counter()
        self._inbox = collections.deque()

    def handle_output(self, report: bytes) -> None:
        report = bytes(report)
        self.sent.append(report)
        key = command_key(report)
        if key is not None and key[0] == "destructive":
            self.destructive.append(report)
            return
        groups = self.trace.responses(key) if key is not None else []
        if not groups:
            self.unmatched.append(report)
            return
        # The k-th time the same command is sent, answer with the k-th recording
        # (the last one repeats), so repeated queries behave as they did on the wire.
        if self.strict and self._seen[key] >= len(groups):
            self.unmatched.append(report)   # e.g. a page that was never recorded: do not invent it from the last one
            return
        group = groups[min(self._seen[key], len(groups) - 1)]
        self._seen[key] += 1
        for i, reply in enumerate(group):
            if self.fault is not None:
                reply = self.fault(key, i, reply)
                if reply is None:
                    continue
            self._inbox.append(reply)

    def poll(self) -> Optional[bytes]:
        return self._inbox.popleft() if self._inbox else None

    def opcodes_sent(self) -> List[int]:
        output = []
        for report in self.sent:
            payload = report[2:] if report[:2] == b"\x7d\x81" else report
            output.append(payload[0] if payload else -1)
        return output


class VirtualClock:
    """Stand-in for the ``time`` module: sleep() advances time instantly."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)

    def patch(self):
        return mock.patch("fiedle400.engine.device.time", self)


UEVENT = (
    "DRIVER=hid-generic\n"
    "HID_ID=0003:000028E9:0000028A\n"
    "HID_NAME=Pulse Oximeter (simulated)\n"
    "HID_PHYS=usb-sim-1/input0\n"
    "HID_UNIQ=\n"
    "MODALIAS=hid:b0003g0001v000028E9p0000028A\n"
)


class HidrawSim:
    """Context manager: the real LinuxHidrawBackend talks to a FakeOximeter through a fake hidraw node."""

    NODE = "hidraw7"

    def __init__(self, fake: FakeOximeter, present: bool = True):
        self.fake = fake
        self.present = present
        self.open_flags: List[int] = []
        self.opened = 0
        self._temporary = None
        self._host = None
        self._device = None
        self._patches = []

    # -- paths ------------------------------------------------------------
    @property
    def device_path(self) -> str:
        return os.path.join(self._temporary, "dev", self.NODE)

    @property
    def sysfs_root(self) -> str:
        return os.path.join(self._temporary, "sys", "class", "hidraw")

    def _build_tree(self) -> None:
        usb = os.path.join(self._temporary, "sys", "devices", "pci0", "usb1", "1-1")
        hid_device = os.path.join(usb, "1-1:1.0", "0003:28E9:028A.0001")
        os.makedirs(hid_device)
        with open(os.path.join(hid_device, "uevent"), "w") as file:
            file.write(UEVENT)
        with open(os.path.join(usb, "manufacturer"), "w") as file:
            file.write("Contec Medical Systems (simulated)\n")
        with open(os.path.join(usb, "product"), "w") as file:
            file.write("Pulse Oximeter\n")
        node_directory = os.path.join(self.sysfs_root, self.NODE)
        os.makedirs(node_directory)
        os.symlink(hid_device, os.path.join(node_directory, "device"))
        os.makedirs(os.path.join(self._temporary, "dev"))
        with open(self.device_path, "w"):
            pass
        os.chmod(self.device_path, 0o666)

    # -- lifecycle --------------------------------------------------------
    def __enter__(self) -> "HidrawSim":
        from fiedle400 import hid_driver
        self._temporary = tempfile.mkdtemp(prefix="hidrawsim-")
        os.makedirs(self.sysfs_root, exist_ok=True)
        if self.present:
            self._build_tree()
        else:
            os.makedirs(os.path.join(self._temporary, "dev"))
        # SOCK_SEQPACKET keeps message boundaries and returns EAGAIN when empty,
        # which is what a non-blocking hidraw read does.
        self._host, self._device = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self._host.setblocking(False)
        host_file_descriptor = self._host.fileno()
        real_open, real_read, real_write = os.open, os.read, os.write
        simulator = self

        def simulator_open(path, flags, *args, **kwargs):
            if os.fspath(path) == simulator.device_path:
                if simulator.fake.unplugged:
                    raise OSError(errno.ENODEV, "No such device", str(path))
                simulator.open_flags.append(flags)
                simulator.opened += 1
                return host_file_descriptor
            return real_open(path, flags, *args, **kwargs)

        def simulator_write(file_descriptor, data):
            if file_descriptor == host_file_descriptor:
                if simulator.fake.unplugged:
                    raise OSError(errno.ENODEV, "No such device")
                if len(data) != REPORT_LENGTH:
                    raise OSError(errno.EINVAL, f"hidraw sim expects {REPORT_LENGTH}-byte reports, got {len(data)}")
                simulator.fake.handle_output(data)
                while True:
                    report = simulator.fake.poll()
                    if report is None:
                        break
                    simulator._device.send(report)
                return len(data)
            return real_write(file_descriptor, data)

        def simulator_read(file_descriptor, size):
            if file_descriptor == host_file_descriptor:
                if simulator.fake.unplugged:
                    raise OSError(errno.ENODEV, "No such device")
            return real_read(file_descriptor, size)

        from fiedle400.engine import device as device_module
        self._patches = [
            mock.patch.object(hid_driver, "SYSFS_HIDRAW_ROOT", self.sysfs_root),
            mock.patch.object(hid_driver, "DEVICE_ROOT", os.path.join(self._temporary, "dev")),
            mock.patch.object(os, "open", simulator_open),
            mock.patch.object(os, "write", simulator_write),
            mock.patch.object(os, "read", simulator_read),
            # T-088: FakeOximeter/this socketpair aren't safe for a second thread to read from
            # concurrently -- tell SerialDeviceEngine not to start its background reader thread
            # even when a test drives real CLI code that asks for one.
            mock.patch.object(device_module, "SIMULATED_DEVICE_ACTIVE", True),
        ]
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *error) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()
        for endpoint_socket in (self._host, self._device):
            try:
                endpoint_socket.close()
            except OSError:
                pass
        shutil.rmtree(self._temporary, ignore_errors=True)

    # -- events -----------------------------------------------------------
    def unplug(self) -> None:
        """Cable pulled: the node disappears and any open handle starts failing with ENODEV."""
        self.fake.unplugged = True
        shutil.rmtree(os.path.join(self.sysfs_root, self.NODE), ignore_errors=True)
        try:
            os.unlink(self.device_path)
        except OSError:
            pass


# --------------------------------------------------------------------------
# A fake `hid` module, for HidBackend (Windows and macOS's real code path)
# --------------------------------------------------------------------------
#
# HidBackend never touches a kernel node directly -- it only ever calls plain
# Python methods on whatever `import hid` gives it: `hid.enumerate(vid, pid)`,
# then either `hid.Device(...)` (the ctypes-wrapper shape, apmorton/pyhidapi,
# PyPI package `hid`) or `hid.device()` + `.open_path()` (the cython shape,
# trezor/cython-hidapi, PyPI package `hidapi` -- what build-release.yml
# installs and what the shipped binary actually uses). Faking it needs no
# kernel/file-descriptor emulation at all, unlike HidrawSim above: it is
# exactly the same FakeOximeter behind a different, much thinner adapter.


class FakeHidDevice:
    """Stands in for a connected `hid.Device` / `hid.device` instance.

    Both object shapes converge on the same four calls once connected:
    write(bytes) -> int, read(n) -> bytes-like, close(), and a `nonblocking`
    attribute/method HidBackend sets but this fake does not need to act on
    (FakeOximeter.poll() never blocks).
    """

    def __init__(self, fake: FakeOximeter):
        self._fake = fake

    # cython-style (`hid.device()` then connect): both accepted, both no-ops
    # beyond recording that *a* path was used -- FakeOximeter does not care.
    def open_path(self, path) -> None:
        pass

    def open(self, vid: int, pid: int) -> None:
        pass

    def set_nonblocking(self, flag) -> None:
        pass

    def write(self, payload: bytes) -> int:
        payload = bytes(payload)
        # HidBackend.write_report prepends a 0x00 HID report-ID byte to every
        # unnumbered 64-byte report (PROTOCOL.md's reports carry no report ID
        # of their own). On real Windows/macOS hidapi that byte is consumed by
        # the HID transport before the data reaches the device's own report
        # buffer -- the firmware never sees it -- so it is stripped here too.
        # Getting the prepend condition wrong anywhere is not silently
        # tolerated: a mis-framed report fails command_key() and surfaces as
        # an entry in FakeOximeter.unmatched, exactly as an unanswered command
        # would.
        if len(payload) == 65 and payload[0] == 0x00:
            payload = payload[1:]
        self._fake.handle_output(payload)
        return len(payload)

    def read(self, max_bytes: int = 64):
        report = self._fake.poll()
        return bytes(report) if report else b""

    def close(self) -> None:
        pass


def make_fake_hid_module(fake: FakeOximeter, style: str = "cython", present: bool = True):
    """A `types.SimpleNamespace` standing in for the whole `hid` module.

    style:
      "cython" -- exposes `hid.device` (what PyPI `hidapi` provides; the shape
                  CI and the shipped binary actually use).
      "ctypes" -- exposes `hid.Device` (what PyPI `hid` provides).
    present: False makes `enumerate()` return [], as it would with no device
             attached or the wrong VID/PID -- HidBackend should then raise
             "no device found", not crash.

    Use with `unittest.mock.patch.dict(sys.modules, {"hid": make_fake_hid_module(...)})`,
    the same pattern tests/test_hid_driver.py already uses for its one-off mocks.
    """
    import types

    def _enumerate(vid: int, pid: int):
        if not present:
            return []
        return [{
            "path": b"fake-hid-path",
            "vendor_id": vid,
            "product_id": pid,
            "product_string": "Pulse Oximeter",
            "manufacturer_string": "",
        }]

    module = types.SimpleNamespace(enumerate=_enumerate)
    if style == "ctypes":
        module.Device = lambda *args, **kwargs: FakeHidDevice(fake)
    elif style == "cython":
        module.device = lambda: FakeHidDevice(fake)
    else:
        raise ValueError(f"unknown style: {style!r}")
    return module
