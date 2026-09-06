"""USB VID/PID hardware decoders and known device profiles."""

from typing import Tuple, Dict

KNOWN_DEVICES: Dict[str, Tuple[str, str]] = {
    "28E9:028A": (
        "GigaDevice MCU HID Oximeter (CMS-60D v2 / Pulsox PO-400)",
        "SpO2_Assistant_v3_Setup.exe INF file hid_device.inf & USB-IF 0x28E9 Registry"
    ),
    "10C4:EA60": (
        "Silicon Labs CP210x USB-to-UART (CMS-50D+)",
        "SpO2_Assistant_v3_Setup.exe INF file SiUSBXp.inf & atbrask/CMS50Dplus project"
    ),
    "0403:6001": (
        "FTDI FT232 Serial Oximeter (Legacy CMS-50/60 Models)",
        "Subsurface-divelog project & Linux usb.ids database"
    ),
}

HARDWARE_PROFILES = KNOWN_DEVICES


def decode_usb_vid_pid(vid_hex: str, pid_hex: str) -> Tuple[str, str]:
    """Decodes a USB Vendor & Product ID (VID:PID) into known pulse oximeter hardware architecture.
    
    Returns:
        tuple: (architecture_description, source_citation)
    """
    vid_clean = vid_hex.upper().replace("0X", "")[-4:].zfill(4)
    pid_clean = pid_hex.upper().replace("0X", "")[-4:].zfill(4)
    key = f"{vid_clean}:{pid_clean}"
    
    return KNOWN_DEVICES.get(
        key,
        ("Unknown USB Device", "Unregistered in Contec/Pulsox driver database")
    )
