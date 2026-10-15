"""Internal Serial Packet Engine facade for backward compatibility.

This module re-exports components from `fiedle400.engine` and `fiedle400.protocol`.
New code should import directly from `fiedle400.engine`.
"""

from .engine import (
    SerialByteStreamBuffer,
    SerialPacketDetector,
    SerialDeviceEngine,
    DecodedPacket,
)
from .protocol import (
    DataPoint,
    SessionInfo,
    DeviceInfo,
    Parsers,
    Commands,
    decode_status_flags,
)

__all__ = [
    "SerialByteStreamBuffer",
    "SerialPacketDetector",
    "SerialDeviceEngine",
    "DecodedPacket",
    "DataPoint",
    "SessionInfo",
    "DeviceInfo",
    "Parsers",
    "Commands",
    "decode_status_flags",
]
