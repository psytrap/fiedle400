"""Subframe bitmask unmasking, delta-nibble decompression, and status flag decoding."""

from typing import List, Optional, Union, Dict, Any


def unmask_subframe_msb(chunk: Union[bytes, bytearray]) -> bytearray:
    """Restores Bit 7 (MSB) for payload bytes 8..28 using mask bytes 5 (m0), 6 (m1), and 7 (m2).

    Unmasking formula:
        Bytes 8..14:  B[i] |= ((m0 << (15 - i)) & 0x80) -> Bit (i - 8) of m0
        Bytes 15..21: B[i] |= ((m1 << (22 - i)) & 0x80) -> Bit (i - 15) of m1
        Bytes 22..28: B[i] |= ((m2 << (29 - i)) & 0x80) -> Bit (i - 22) of m2
    """
    if len(chunk) < 29:
        return bytearray()

    m0, m1, m2 = chunk[5], chunk[6], chunk[7]
    unmasked = bytearray(chunk[8:29])
    for i in range(7):
        if (m0 >> i) & 1:
            unmasked[i] |= 0x80
        if (m1 >> i) & 1:
            unmasked[i + 7] |= 0x80
        if (m2 >> i) & 1:
            unmasked[i + 14] |= 0x80
    return unmasked


def decode_status_flags(flags: int) -> str:
    """Decode PO-400 status/quality flags byte into human-readable string.

    Known flag bits:
        bit 4 (0x10): Probe disconnected / finger out
        bit 5 (0x20): Pulse search / signal invalid
        bit 6 (0x40): Low perfusion index
        0x30 (0x10|0x20): Probe out + searching = "probe-out"
        0x00: Normal / valid reading
    """
    if flags == 0x00:
        return "ok"
    parts = []
    if flags & 0x10 or (flags & 0x0F == 0x0F):
        parts.append("probe-out")
    if flags & 0x20:
        parts.append("searching")
    if flags & 0x40:
        parts.append("low-perfusion")
    unknown = flags & ~0x70
    if unknown and not (flags & 0x0F == 0x0F):
        parts.append(f"0x{unknown:02x}")
    return ",".join(parts) if parts else f"0x{flags:02x}"


def decode_ed_subframes(
    subframes: List[bytes],
    is_spo2: bool = True,
    state: Optional[Dict[str, Any]] = None,
) -> List[Optional[int]]:
    """Decodes delta-compressed samples (one per second, T-075) from a sequence of 30-byte 0xED 0x04 subframes.

    Reversed from SpO2.exe (0x004c4fa7) and verified on PO-400 hardware:
    - Restores Bit 7 for bytes 8..28 via m0 (5), m1 (6), m2 (7).
    - Detects 0xF_ 0xF_ dynamic base value escape: ((B1 & 0x0F) << 4) | (B2 & 0x0F).
    - Supports cross-subframe split-base (when B1 is at byte index 28).
    - Stops on 0xFF 0xFF terminator ("遇到无效包，结束").
    - Decompresses two samples per byte, one second apart (SpO2.exe 0x4e9b49):
        Sample 1 = BaseValue - (B >> 4)
        Sample 2 = BaseValue - (B & 0x0F)  (skipped if Low-Nibble == 0x0F padding)
    - Validates physiological ranges:
        SpO2: 1..100 (out-of-range -> None for probe-out)
        HR:   1..254 (out-of-range -> None for probe-out)
    """
    samples: List[Optional[int]] = []
    base_value: Optional[int] = state.get("base_value") if state else None
    pending_split: Optional[int] = state.get("pending_split") if state else None

    for subframe in subframes:
        if len(subframe) < 30 or subframe[0] != 0xED or subframe[1] != 0x04:
            continue

        unmasked = unmask_subframe_msb(subframe)
        position = 0
        while position < len(unmasked):
            byte = unmasked[position]

            if pending_split is not None:
                base_value = pending_split | (byte & 0x0F)
                pending_split = None
                position += 1
                continue

            if (byte & 0xF0) == 0xF0:
                if position == len(unmasked) - 1:
                    pending_split = (byte & 0x0F) << 4
                    position += 1
                    continue
                next_byte = unmasked[position + 1]
                if byte == 0xFF and next_byte == 0xFF:
                    if state is not None:
                        state["base_value"] = base_value
                        state["pending_split"] = pending_split
                    return samples
                if (next_byte & 0xF0) == 0xF0:
                    base_value = ((byte & 0x0F) << 4) | (next_byte & 0x0F)
                    position += 2
                    continue

            if base_value is None:
                base_value = 98 if is_spo2 else 60

            high_nibble = (byte >> 4) & 0x0F
            low_nibble = byte & 0x0F

            high_sample = base_value - high_nibble
            low_sample = (base_value - low_nibble) if (low_nibble != 0x0F) else None

            if is_spo2:
                high_value = high_sample if (0 < high_sample <= 100) else None
                low_value = low_sample if (low_sample is not None and 0 < low_sample <= 100) else None
            else:
                high_value = high_sample if (0 < high_sample <= 254) else None
                low_value = low_sample if (low_sample is not None and 0 < low_sample <= 254) else None

            samples.append(high_value)
            if low_sample is not None:
                samples.append(low_value)
            position += 1

    if state is not None:
        state["base_value"] = base_value
        state["pending_split"] = pending_split

    return samples
