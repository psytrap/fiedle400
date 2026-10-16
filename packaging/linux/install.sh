#!/bin/sh
# User-local install for the fiedle400 standalone Linux binary. Never needs
# root: it only touches files under the current user's home directory.
#
# Usage, run from the directory containing the downloaded binary and this
# script (both ship together in the Linux release asset):
#   ./install.sh              install (binary, PATH note, desktop launcher)
#   ./install.sh --uninstall  remove ~/.local/bin/fiedle400 and the launcher, and
#                             offer to remove the saved settings (asks first)
#
# Device access (udev rules) is a SEPARATE, deliberately root-requiring step:
# see fiedle400_setup-udev.sh, shipped alongside this script. install.sh does
# not run it and does not invoke sudo -- it only tells you the command.

set -eu

CONFIG_BASE="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/fiedle400.desktop"
WORK_DIR="$HOME/Documents/fiedle400"
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
    if [ -f "$BIN_DIR/fiedle400" ]; then
        rm -f "$BIN_DIR/fiedle400"
        echo "Removed $BIN_DIR/fiedle400"
    else
        echo "Nothing to remove: $BIN_DIR/fiedle400 does not exist."
    fi
    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        echo "Removed $DESKTOP_FILE"
        command -v update-desktop-database >/dev/null 2>&1 && \
            update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
    fi
    # Saved settings (and po400's, from before the rename). Recordings in
    # $WORK_DIR are never touched: they are your data.
    for dir in "$CONFIG_BASE/fiedle400" "$CONFIG_BASE/po400"; do
        [ -d "$dir" ] || continue
        printf "Remove saved settings %s? [y/N]: " "$dir"
        read -r ans || ans="n"
        case "$ans" in
            y|Y|yes|Yes) rm -rf "$dir"; echo "Removed $dir" ;;
            *) echo "Kept $dir" ;;
        esac
    done
    if [ -d "$WORK_DIR" ]; then
        echo "Your recordings in $WORK_DIR were not touched; delete that folder"
        echo "yourself if you no longer need them."
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

mkdir -p "$APPS_DIR" "$WORK_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=fiedle400
Comment=Pulsox PO-400 pulse oximeter: download and plot recordings
Exec=$BIN_DIR/fiedle400
Path=$WORK_DIR
Icon=utilities-system-monitor
Terminal=true
Categories=Utility;
EOF
chmod +x "$DESKTOP_FILE"
echo "Installed desktop launcher: $DESKTOP_FILE (opens a terminal in $WORK_DIR)"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

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
