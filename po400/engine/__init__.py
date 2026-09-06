"""Serial Packet Engine package for Pulsox PO-400 / CMS-60D Pulse Oximeters.

Provides stream buffering, packet detection, and high-level device controller workflows.
"""

from .buffer import SerialByteStreamBuffer
from .detector import SerialPacketDetector
from .device import SerialDeviceEngine
from ..protocol import DecodedPacket

__all__ = [
    "SerialByteStreamBuffer",
    "SerialPacketDetector",
    "SerialDeviceEngine",
    "DecodedPacket",
]
