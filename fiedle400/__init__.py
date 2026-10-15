"""Pulsox PO-400 USB HID Pulse Oximeter Package"""

__version__ = "0.3.1"

from .engine import (
    SerialByteStreamBuffer,
    SerialPacketDetector,
    SerialDeviceEngine,
    DecodedPacket,
)
from .export import (
    export_records,
    build_spo2_binary,
)


def __getattr__(name):
    # plot needs matplotlib (optional extra), so import it only on first use.
    if name == "plot_session":
        from .plot import plot_session
        return plot_session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SerialByteStreamBuffer",
    "SerialPacketDetector",
    "SerialDeviceEngine",
    "DecodedPacket",
    "export_records",
    "build_spo2_binary",
    "plot_session",
    "__version__",
]
