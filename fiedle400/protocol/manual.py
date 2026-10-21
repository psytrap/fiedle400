"""Manual-mode recordings (PROTOCOL.md §3.14, T-042): commands, the 0xD0 header and the subframe decoder.

A PO-400 switched to Manual recording mode keeps one recording, read with its own commands
instead of 0x9C/0x9D. Layouts follow SpO2 Assistant's handlers (SpO2.exe: header parser
0x4e92ac, SpO2 subframe decoder 0x4e9440, pulse 0x4e97ce, download dialog cases 0x4b6c46 /
0x4b75c6) and the capture archive/capture/bum400_20261015_194301.pcap.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

HEADER = 0xD0
SPO2_DATA = 0xD3
PULSE_DATA = 0xD2
BLOCK_ACK = 0xD8
SPO2_REQUEST = 0xA3
PULSE_REQUEST = 0xA2
DELETE_REQUEST = 0xA1
DELETE_REPLY = 0xD1

SUBFRAME_LEN = 20
SAMPLES_PER_SUBFRAME = 27   # 1 base value + 13 bytes of two deltas each
NO_SPO2 = 0x7F              # invalid / no finger, as SpO2.exe stores it
NO_PULSE = 0xFF

# Frame lengths of everything that can share a report with the manual-mode replies.
_FRAME_LEN = {HEADER: 14, SPO2_DATA: SUBFRAME_LEN, PULSE_DATA: SUBFRAME_LEN, BLOCK_ACK: 4,
              DELETE_REPLY: 4, 0xEB: 6, 0xF0: 2}


def _report(*body: int) -> bytes:
    """A raw (unprefixed) command as SpO2 Assistant sends it: body, 7-bit checksum, zero padding."""
    b = list(body) + [sum(body) & 0x7F]
    return bytes(b + [0] * (64 - len(b)))


def header_query() -> bytes:
    """`A0 00 20`: ask for the manual recording's header (answered by 0xD0)."""
    return _report(0xA0, 0x00)


def series_request(opcode: int, start_subframe: int = 0) -> bytes:
    """`A3 00 lo hi` (SpO2) / `A2 00 lo hi` (pulse): send the series from that subframe on."""
    return _report(opcode, 0x00, start_subframe & 0x7F, (start_subframe >> 7) & 0x7F)


def series_end(opcode: int) -> bytes:
    """`A3 7F 00 00` / `A2 7F 00 00`: stop sending that series (also ends the download)."""
    return _report(opcode, 0x7F, 0x00, 0x00)


def block_ack(is_spo2: bool) -> bytes:
    """`A7 01 28` after the SpO2 series, `A7 00 27` after the pulse series (answered by 0xD8)."""
    return _report(0xA7, 0x01 if is_spo2 else 0x00)


def delete_step(step: int) -> bytes:
    """`A1 00` / `A1 01` / `A1 04`: SpO2.exe's Manual-mode erase (PROTOCOL.md 3.14 G, T-072).

    Static analysis only -- never seen on the wire. Each step is answered by `D1 [step] [status]`;
    SpO2.exe sends the next step after a status-0 reply, and `A1 04` only when a third-series flag
    is set that has no known Manual-mode equivalent (so `clear_memory` never sends it, PROTOCOL.md
    3.14 G "Not confirmed").
    """
    return _report(DELETE_REQUEST, step)


def parse_delete_reply(frame: bytes) -> Optional[Tuple[int, int]]:
    """`D1 [step] [status] [chk]` -> `(step, status)`; status 0 means that step is done."""
    if len(frame) < 4 or frame[0] != DELETE_REPLY or not _checksum_ok(frame[:4]):
        return None
    return frame[1], frame[2]


def _checksum_ok(frame: bytes) -> bool:
    return (sum(frame[:-1]) & 0x7F) == frame[-1]


def frames(reports: Iterable[bytes]) -> List[bytes]:
    """Splits device reports into frames, keeping the manual-mode ones with a valid checksum.

    Live-stream (0xEB) and acknowledgement (F0 70) frames and the zero padding are skipped.
    """
    stream = b"".join(bytes(r) for r in reports)
    out, i = [], 0
    while i < len(stream):
        op = stream[i]
        n = _FRAME_LEN.get(op)
        if n is None:
            i += 1
            continue
        frame = stream[i:i + n]
        if len(frame) == n and op in (HEADER, SPO2_DATA, PULSE_DATA, BLOCK_ACK, DELETE_REPLY) and _checksum_ok(frame):
            out.append(frame)
        i += n
    return out


@dataclass
class ManualHeader:
    start: Optional[datetime]
    samples: int          # one per second
    kind: int             # byte 1; 0 in the only capture (other values select other decoders in SpO2.exe)


def parse_header(frame: bytes) -> Optional[ManualHeader]:
    """`D0 kind YY MM DD hh mm ss ?? ?? n0 n1 n2 chk`: the sample count is 7-bit little-endian."""
    if len(frame) < 14 or frame[0] != HEADER or not _checksum_ok(frame[:14]):
        return None
    samples = frame[10] | (frame[11] << 7) | (frame[12] << 14)
    try:
        start = datetime(2000 + frame[2], frame[3], frame[4], frame[5], frame[6], frame[7])
    except ValueError:
        start = None
    return ManualHeader(start=start, samples=samples, kind=frame[1])


def subframe_seq(frame: bytes) -> int:
    return frame[1] | (frame[2] << 7)


def decode_subframe(frame: bytes) -> List[int]:
    """Always 27 values, as SpO2.exe decodes them: invalid ones are 0x7F (SpO2) or 0xFF (pulse).

    Byte 5 is the first value; bytes 6..18 each hold two deltas, high nibble first, as sign
    (bit 3) and magnitude (bits 0..2). A negative 7 (nibble 0xF) marks an invalid sample, and
    the deltas after it build on that invalid value, so they stay invalid until the subframe
    ends. That is how a recording ends inside a subframe (0x7F filler bytes).
    """
    is_spo2 = frame[0] == SPO2_DATA
    bad, hi = (NO_SPO2, 100) if is_spo2 else (NO_PULSE, 254)
    base = frame[5]
    if base <= 0 or base > hi:
        base = bad
    if base == bad:
        return [bad] * SAMPLES_PER_SUBFRAME
    vals = [base]
    for byte in frame[6:6 + (SAMPLES_PER_SUBFRAME - 1) // 2]:
        for nib in (byte >> 4, byte & 0x0F):
            mag = nib & 7
            if nib & 8:
                vals.append(bad if mag == 7 else (vals[-1] - mag) & 0xFF)
            else:
                vals.append((vals[-1] + mag) & 0xFF)
    return [v if 0 < v <= hi else bad for v in vals]


def records(spo2: List[int], pulse: List[int], samples: int) -> List[Tuple[Optional[int], Optional[int]]]:
    """(SpO2, pulse) per second; both None where the SpO2 sample is invalid (no finger).

    The pulse decoder keeps "valid" bytes after an invalid sample (0xFF + 7 wraps to 6), so a
    pulse value only counts where SpO2 has one.
    """
    out = []
    for i in range(samples):
        s = spo2[i] if i < len(spo2) else NO_SPO2
        p = pulse[i] if i < len(pulse) else NO_PULSE
        if s == NO_SPO2:
            out.append((None, None))
        else:
            out.append((s, None if p == NO_PULSE else p))
    return out
