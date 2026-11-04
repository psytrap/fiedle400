"""Protocol B: the Contec protocol of the PO-250 and the CMS50F v3.7 family (PROTOCOL_B.md).

fiedle400 downloads from a PO-250 in this protocol (T-105) and refuses every device that names
itself CMS50* (CMS50F FW 3.7, CMS50I, CMS50H; `is_refused_model`). A different protocol from the
PO-400's (CMS50_COMPATIBILITY.md §2), taken from OSCAR's `cms50f37_loader.cpp`, Contec's
"Communication Protocol of Pulse Oximeter V7.0" and kaivol/pulox (written against a PO-250), and
checked byte for byte against a real CMS50F 3.7 download by SpO2 Assistant 2.x
(CMS50_COMPATIBILITY.md §6, `tests/fixtures/cms50f37-download.trace.json`):

- Requests are always 9 bytes: `7D 81 [op] [user] [session] 80 80 80 80`, every byte after the
  prefix with bit 7 set, no checksum.
- Replies are `[code 00..1F] [high bits] [data...]`; the length depends on the code (`LENGTHS`).
  Bit k of the second byte is bit 7 of data byte k.

Only read-only commands are here. `0xAE` (erase a recording) and `0xAA` (device identifier in
protocol B, but `FLASH_CLEAR` in the PO-400's protocol) are deliberately left out and never sent.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

HELLO1 = 0xA7            # stop stored data stream; answered with code 0x0C
HELLO2 = 0xA2            # stop live data stream; answered with code 0x0C
SESSION_COUNT = 0xA3     # code 0x0A: user index, number of recordings
SESSION_LENGTH = 0xA4    # code 0x08: recording length in bytes, 2 per sample
SESSION_TIME = 0xA5      # codes 0x07 (date) and 0x12 (time)
SESSION_DATA = 0xA6      # codes 0x0F (3 samples) or 0x09 (1 sample with PI)
MODEL = 0xA8             # code 0x02, two frames
USER_COUNT = 0xAD        # code 0x10: number of users

REPLY_MODEL = 0x02
REPLY_DATE = 0x07
REPLY_LENGTH = 0x08
REPLY_DATA_PI = 0x09
REPLY_COUNT = 0x0A
REPLY_HELLO = 0x0C
REPLY_DATA = 0x0F
REPLY_USER_COUNT = 0x10
REPLY_TIME = 0x12

BYTES_PER_SAMPLE = 2  # A4 counts bytes; one (SpO2, pulse) sample per second (kaivol, capture)
INVALID_PULSE = 0xFF  # a sample with this pulse value has no reading (OSCAR)

# Frame length per reply code (OSCAR's table). 0 = not a reply code.
LENGTHS = (0, 0, 9, 9, 9, 9, 4, 8, 8, 6, 4, 4, 2, 0, 3, 8, 3, 9, 8, 9, 9) + (0,) * 11


@dataclass(frozen=True)
class Frame:
    """One protocol-B reply frame: a code and its data bytes, bit 7 already restored.

    Internal to this protocol -- not the same thing as `protocol.models.DecodedPacket`, the
    protocol-agnostic interface (PROTOCOL_B.md §3); `engine.cms50f37.Cms50F37Engine` turns these
    into fiedle400's records. Protocol C has no equivalent raw-frame stage to share this with: its
    `SerialPacketDetector` decodes straight from bytes to `DecodedPacket`.
    """
    code: int
    data: bytes


def build_command(opcode: int, session: int = 0, user: int = 0) -> bytes:
    """A 9-byte request. Session and user indexes start at 0 (OSCAR puts the session in byte 4)."""
    return bytes([0x7D, 0x81, opcode | 0x80, (user & 0x7F) | 0x80, (session & 0x7F) | 0x80,
                  0x80, 0x80, 0x80, 0x80])


def split_frames(buffer: bytes, strict: bool = False) -> Tuple[List[Frame], bytes]:
    """Cuts a byte stream into Frames, data with bit 7 restored.

    Bytes that cannot start a frame are skipped. With `strict`, so are frames whose bytes after
    the code do not all have bit 7 set, as every real protocol-B frame does: that keeps random
    bytes from a foreign device from passing for a reply. Returns the frames and the incomplete
    rest.
    """
    frames: List[Frame] = []
    i = 0
    while i < len(buffer):
        code = buffer[i]
        length = LENGTHS[code] if code < len(LENGTHS) else 0
        if length == 0:
            i += 1
            continue
        if i + length > len(buffer):
            break
        if strict and not all(byte & 0x80 for byte in buffer[i + 1:i + length]):
            i += 1
            continue
        high = buffer[i + 1]
        data = bytes((byte & 0x7F) | (0x80 if (high >> k) & 1 else 0) for k, byte in enumerate(buffer[i + 2:i + length]))
        frames.append(Frame(code, data))
        i += length
    return frames, bytes(buffer[i:])


def _text(data: bytes) -> str:
    return data.replace(b"\x00", b" ").decode("ascii", errors="replace").strip()


def model_from_frames(frames: List[Frame]) -> Optional[str]:
    """The model string from the `0x02` frames: the first carries data[0] == 0, a second one
    (data[0] != 0) may continue it. None if no `0x02` frame came."""
    parts = [(frame.data[0], frame.data[1:7]) for frame in frames if frame.code == REPLY_MODEL and len(frame.data) >= 7]
    if not parts:
        return None
    first = next((text for k, text in parts if k == 0), parts[0][1])
    extra = b"".join(text for k, text in parts if k != 0)
    model = (_text(first) + _text(extra)).strip()
    return model or None


def is_refused_model(model: Optional[str]) -> bool:
    """True for a protocol-B device fiedle400 does not support: anything naming itself CMS50*
    (CMS50F v3.7, CMS50I, CMS50H). Any other answer, or none, is taken as a PO-250 (psytrap,
    2026-11-04): the PO-250's own `A8` string is still unknown (kaivol/pulox never asks)."""
    return bool(model) and model.strip().upper().startswith("CMS50")


def session_count(frames: List[Frame]) -> Optional[Tuple[int, int]]:
    """(user index, number of recordings) from the `0x0A` reply."""
    for frame in frames:
        if frame.code == REPLY_COUNT and len(frame.data) >= 2:
            return frame.data[0], frame.data[1]
    return None


def session_length(frames: List[Frame]) -> Optional[int]:
    """The recording length in bytes from the `0x08` reply (bytes 2..5, little-endian)."""
    for frame in frames:
        data = frame.data
        if frame.code == REPLY_LENGTH and len(data) >= 6:
            return data[2] | (data[3] << 8) | (data[4] << 16) | (data[5] << 24)
    return None


@dataclass
class SessionStart:
    year: int
    month: int
    day: int
    hour: Optional[int] = None
    minute: Optional[int] = None
    second: Optional[int] = None

    def as_datetime(self) -> Optional[datetime]:
        """None if the device sent no usable date or time."""
        if self.year == 0 or self.hour is None:
            return None
        try:
            return datetime(self.year, self.month, self.day, self.hour, self.minute or 0, self.second or 0)
        except ValueError:
            return None


def session_start(frames: List[Frame]) -> Optional[SessionStart]:
    """Date (`0x07`: century and year of century, month, day) and time (`0x12`: hour, minute,
    second). The capture's `14 0E 08 03` is 2014-08-03: kaivol's 16-bit year would read 3604."""
    start = None
    for frame in frames:
        data = frame.data
        if frame.code == REPLY_DATE and len(data) >= 6:
            start = SessionStart(year=data[2] * 100 + data[3], month=data[4], day=data[5])
    if start is None:
        return None
    for frame in frames:
        data = frame.data
        if frame.code == REPLY_TIME and len(data) >= 5:
            start.hour, start.minute, start.second = data[2], data[3], data[4]
    return start


def samples(frame: Frame) -> List[Tuple[Optional[int], Optional[int]]]:
    """(SpO2, pulse) pairs of one data frame; (None, None) for a sample without a reading.

    `0x0F` holds three samples; `0x09` holds one sample plus a perfusion index, which fiedle400
    does not keep. Any other code holds none.
    """
    data = frame.data
    if frame.code == REPLY_DATA:
        pairs = [(data[k], data[k + 1]) for k in range(0, min(len(data), 6) - 1, 2)]
    elif frame.code == REPLY_DATA_PI and len(data) >= 2:
        pairs = [(data[0], data[1])]
    else:
        return []
    out: List[Tuple[Optional[int], Optional[int]]] = []
    for spo2, pulse in pairs:
        if pulse == INVALID_PULSE or spo2 == 0 or spo2 > 100 or pulse == 0:
            out.append((None, None))
        else:
            out.append((spo2, pulse))
    return out
