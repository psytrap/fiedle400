#!/bin/sh
# User-local install for the fiedle400 standalone Linux binary. Never needs
# root: it only touches files under the current user's home directory.
#
# Usage, run from the directory containing the downloaded binary and this
# script (both ship together in the Linux release asset):
#   ./install.sh              install
#   ./install.sh --uninstall  remove ~/.local/bin/fiedle400
#
# Device access (udev rules) is a SEPARATE, deliberately root-requiring step:
# see fiedle400_setup-udev.sh, shipped alongside this script. install.sh does
# not run it and does not invoke sudo -- it only tells you the command.

set -eu

BIN_DIR="$HOME/.local/bin"
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
    if [ -f "$BIN_DIR/fiedle400" ]; then
        rm -f "$BIN_DIR/fiedle400"
        echo "Removed $BIN_DIR/fiedle400"
    else
        echo "Nothing to remove: $BIN_DIR/fiedle400 does not exist."
    fi
    echo "The udev rules from fiedle400_setup-udev.sh are not removed by this"
    echo "script (they need root, same as installing them). To remove them:"
    echo "  sudo rm -f /etc/udev/rules.d/99-pulsox*.rules"
    echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
    exit 0
fi

SRC="$HERE/fiedle400"
if [ ! -f "$SRC" ]; then
    echo "Cannot find a 'fiedle400' binary next to this script ($HERE)." >&2
    echo "Download it alongside install.sh from the GitHub Release, or pass" >&2
    echo "its path: FIEDLE400_BIN=/path/to/fiedle400 $0" >&2
    SRC="${FIEDLE400_BIN:-}"
    [ -f "$SRC" ] || exit 1
fi

mkdir -p "$BIN_DIR"
cp "$SRC" "$BIN_DIR/fiedle400"
chmod +x "$BIN_DIR/fiedle400"
echo "Installed: $BIN_DIR/fiedle400"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Note: $BIN_DIR is not on your PATH yet. Add this to your shell's"
        echo "startup file (~/.bashrc, ~/.zshrc, ...) and open a new terminal:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac

UDEV_SCRIPT="$HERE/fiedle400_setup-udev.sh"
echo
echo "Installation complete. Run: fiedle400"
echo
if [ -f "$UDEV_SCRIPT" ]; then
    echo "Before the PO-400 is usable, grant it device access (one-time, needs root):"
    echo "  sudo $UDEV_SCRIPT"
else
    echo "Before the PO-400 is usable, grant it device access (one-time, needs root)."
    echo "fiedle400_setup-udev.sh was not found next to this script -- download it"
    echo "from the same GitHub Release and run: sudo ./fiedle400_setup-udev.sh"
fi
echo "Then verify everything works: fiedle400 selftest"
