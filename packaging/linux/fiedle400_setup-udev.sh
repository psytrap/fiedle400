#!/bin/sh
# Installs the udev rules the PO-400 (VID 28e9, PID 028a) needs for non-root
# HID access on Linux. Deliberately small and standalone -- read it top to
# bottom before running it, since it must run as root.
#
# This script WRITES SYSTEM FILES. It does not:
#   - download or run anything else,
#   - touch any file outside /etc/udev/rules.d/,
#   - modify the fiedle400 binary or its settings.
#
# Usage:
#   sudo ./fiedle400_setup-udev.sh
#
# fiedle400 itself (via `fiedle400 selftest`) only ever points you at this
# script; it never invokes sudo on its own.

set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "This script writes to /etc/udev/rules.d/, which needs root." >&2
    echo "Run it again as:" >&2
    echo "  sudo $0" >&2
    exit 1
fi

VID="28e9"
PID="028a"
RULES_DIR="/etc/udev/rules.d"

write_rule() {
    path="$RULES_DIR/$1"
    content="$2"
    if [ -f "$path" ] && [ "$(cat "$path")" = "$content" ]; then
        echo "Already up to date: $path"
        return
    fi
    printf '%s\n' "$content" > "$path"
    echo "Wrote: $path"
}

# hidraw: the primary access path fiedle400 uses on Linux (--backend hidraw).
# TAG+="uaccess" grants the active console session access via systemd-logind,
# so MODE="0666" below is a fallback, not the primary access mechanism.
write_rule "99-pulsox.rules" \
    "SUBSYSTEM==\"hidraw\", ATTRS{idVendor}==\"$VID\", ATTRS{idProduct}==\"$PID\", MODE=\"0666\", TAG+=\"uaccess\""

# usb: needed by the cross-platform `hid` backend (--backend hid), which on
# Linux goes through libusb rather than the hidraw node directly.
write_rule "99-pulsox-usb.rules" \
    "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$VID\", ATTR{idProduct}==\"$PID\", MODE=\"0666\", TAG+=\"uaccess\""

# tty: only relevant if the device ever enumerates as a serial device instead
# of HID (older firmware variants); harmless to install even if it never
# matches on this hardware.
write_rule "99-pulsox-serial.rules" \
    "SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$VID\", ATTRS{idProduct}==\"$PID\", MODE=\"0666\", GROUP=\"dialout\""

udevadm control --reload-rules
udevadm trigger

echo
echo "Done. If the PO-400 is already plugged in, unplug and reconnect it once"
echo "so the new rule applies, then run: fiedle400 selftest"
