"""Protocol B probe constants: the Contec CMS50F v3.7 family (CMS50F FW 3.7, CMS50I, CMS50H).

Detection only (T-105 is on hold): enough to recognize a protocol-B device during the serial
probe and name it, not to download from it. A different protocol from the PO-400's
(CMS50_COMPATIBILITY.md §2), taken from OSCAR's `cms50f37_loader.cpp` and checked byte for byte
against a real CMS50F 3.7 download by SpO2 Assistant 2.x (CMS50_COMPATIBILITY.md §6):

- Requests are always 9 bytes: `7D 81 [op] [user] [session] 80 80 80 80`, every byte after the
  prefix with bit 7 set, no checksum.
- Replies are `[code 00..1F] [high bits] [data...]`; the length depends on the code (`LENGTHS`).
  Bit k of the second byte is bit 7 of data byte k.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

HELLO1 = 0xA7  # stop stored data stream; answered with code 0x0C
HELLO2 = 0xA2  # stop live data stream; answered with code 0x0C
MODEL = 0xA8   # code 0x02, two frames

REPLY_MODEL = 0x02

# Frame length per reply code (OSCAR's table). 0 = not a reply code.
LENGTHS = (0, 0, 9, 9, 9, 9, 4, 8, 8, 6, 4, 4, 2, 0, 3, 8, 3, 9, 8, 9, 9) + (0,) * 11


@dataclass(frozen=True)
class Frame:
    """One protocol-B reply frame: a code and its data bytes, bit 7 already restored.

    Internal to this protocol -- not the same thing as `protocol.models.DecodedPacket`, which is
    the actual protocol-agnostic interface a future `Cms50f37Engine` would produce from these
    (PROTOCOL_B.md §3). Protocol C has no equivalent raw-frame stage to share this with: its
    `SerialPacketDetector` decodes straight from bytes to `DecodedPacket`.
    """
    code: int
    data: bytes


def build_command(opcode: int, session: int = 0, user: int = 0) -> bytes:
    """A 9-byte request. Session and user indexes start at 0 (OSCAR puts the session in byte 4)."""
    return bytes([0x7D, 0x81, opcode | 0x80, (user & 0x7F) | 0x80, (session & 0x7F) | 0x80,
                  0x80, 0x80, 0x80, 0x80])


def split_frames(buffer: bytes) -> Tuple[List[Frame], bytes]:
    """Cuts a byte stream into Frames, data with bit 7 restored.

    Bytes that cannot start a frame are skipped. Returns the frames and the incomplete rest.
    """
    frames: List[Frame] = []
    i = 0
    while i < len(buffer):
        code = buffer[i]
        length = LENGTHS[code & 0x1F] if code < 0x80 else 0
        if length == 0:
            i += 1
            continue
        if i + length > len(buffer):
            break
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
