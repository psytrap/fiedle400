"""7-Bit modulo-128 checksums and 7-bit Little-Endian integer packing utilities."""

from typing import Tuple, List, Union


def calc_checksum_7bit(data: Union[bytes, bytearray, List[int]]) -> int:
    """Calculates 7-bit Modulo-128 sum checksum: (sum(data)) mod 128."""
    return sum(data) & 0x7F


def pack_7bit_le_14bit(val: int) -> Tuple[int, int]:
    """Packs a 14-bit integer into two 7-bit Little-Endian bytes: (low, high)."""
    return (val & 0x7F, (val >> 7) & 0x7F)


def unpack_7bit_le_14bit(low: int, high: int) -> int:
    """Unpacks two 7-bit Little-Endian bytes into a 14-bit integer."""
    return ((high & 0x7F) << 7) | (low & 0x7F)


def pack_7bit_le_28bit(val: int) -> List[int]:
    """Packs a 28-bit integer into four 7-bit Little-Endian bytes [b0, b1, b2, b3]."""
    return [
        val & 0x7F,
        (val >> 7) & 0x7F,
        (val >> 14) & 0x7F,
        (val >> 21) & 0x7F,
    ]


def unpack_7bit_le_28bit(b0: int, b1: int, b2: int, b3: int) -> int:
    """Unpacks four 7-bit Little-Endian bytes into a 28-bit integer (e.g. 2 Hz sample count)."""
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | ((b2 & 0x7F) << 14) | ((b3 & 0x7F) << 21)
