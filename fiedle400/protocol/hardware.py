"""USB VID/PID hardware decoders and known device profiles."""

from typing import Dict, List, Optional, Tuple

# Every USB ID SpO2 Assistant itself scans for (PROTOCOL.md §5, T-100). An ID says which
# transport to use, not which model: SpO2.exe attaches no model to any of them, and neither
# do we. The model comes from the device's own 0xF1 reply (MODEL_STRINGS below, T-104).
KNOWN_DEVICES: Dict[str, Tuple[str, str]] = {
    "28E9:028A": (
        "GigaDevice MCU HID Oximeter (Pulox PO-400)",
        "SpO2.exe HID scan (PROTOCOL.md §5) & PO-400 USB captures"
    ),
    "0483:5751": (
        "STM32 HID Oximeter (Contec, model unknown)",
        "SpO2.exe HID scan (PROTOCOL.md §5); never seen on a real device"
    ),
    "10C4:EA60": (
        "Silicon Labs CP210x USB-to-UART (Contec CMS50 serial models)",
        "SpO2.exe COM scan (PROTOCOL.md §5) & OSCAR cms50f37_loader.cpp"
    ),
    "1CBE:0002": (
        "USB serial oximeter (Contec, model unknown)",
        "SpO2.exe COM scan (PROTOCOL.md §5); never seen on a real device"
    ),
    "0483:5740": (
        "STM32 virtual COM port oximeter (Contec, model unknown)",
        "SpO2.exe COM scan (PROTOCOL.md §5); never seen on a real device"
    ),
}

# USB IDs per transport, in SpO2.exe's scan order (PROTOCOL.md §5).
HID_USB_IDS: List[Tuple[int, int]] = [(0x28E9, 0x028A), (0x0483, 0x5751)]
SERIAL_USB_IDS: List[Tuple[int, int]] = [(0x10C4, 0xEA60), (0x1CBE, 0x0002), (0x0483, 0x5740)]

# Model strings the device reports in its 0xF1 reply (PROTOCOL.md §3, `81 01`), mapped to the
# product name. Only strings seen on a real device go here; PO-250/PO-300 strings are still
# unknown (T-102), so those devices are shown with their raw string.
MODEL_STRINGS: Dict[str, str] = {
    "50F": "Pulox PO-400",
}


def describe_model(model_string: Optional[str]) -> str:
    """Product name for a 0xF1 model string, never a guess (T-104)."""
    if not model_string:
        return "PO-x00 family device (model not reported)"
    name = MODEL_STRINGS.get(model_string.strip().upper())
    if name:
        return name
    return f"Unknown PO-x00 family device (model string \"{model_string.strip()}\")"


def is_known_model(model_string: Optional[str]) -> bool:
    return bool(model_string) and model_string.strip().upper() in MODEL_STRINGS


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
