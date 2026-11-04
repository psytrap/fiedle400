"""Internal Serial Packet Engine facade for backward compatibility.

This module re-exports components from `fiedle400.engine` and `fiedle400.protocol`.
New code should import directly from `fiedle400.engine`.
"""

from .engine import (
    SerialByteStreamBuffer,
    SerialPacketDetector,
    SerialDeviceEngine,
    Cms50F37Engine,
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


def make_engine(device, background_reader: bool = False):
    """The engine for the protocol the connect probe found: `Cms50F37Engine` for a PO-250 in
    protocol B (T-105, PROTOCOL_B.md), `SerialDeviceEngine` for everything else."""
    if getattr(device, "protocol", "po400") == "cms50f37":
        return Cms50F37Engine(device, background_reader=background_reader)
    return SerialDeviceEngine(device, background_reader=background_reader)


__all__ = [
    "make_engine",
    "Cms50F37Engine",
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
