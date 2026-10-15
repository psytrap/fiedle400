# po400 — Packaging & Distribution Strategy

> **Status: Design / Pre-POC**
> This document records the agreed packaging approach for both Linux and Windows.
> Implementation begins after a proof-of-concept validates the build pipeline.

---

## Core Principle

`po400` is distributed as a **self-contained standalone binary** built with PyInstaller.
No Python installation is required on the end-user machine.

```
pyinstaller po400.spec
    ├── Linux  →  dist/po400          (ELF, ~10–20 MB)
    └── Windows → dist/po400.exe      (PE32, ~10–20 MB)
```

PyInstaller **cannot cross-compile** — each platform's binary must be built on that platform
(or a matching CI runner).

---

## Linux

### Distribution Artifact

```
po400               ← standalone ELF binary
install.sh          ← user-local installer script
```

### `install.sh` Behaviour

| Step | Action |
|------|--------|
| 1 | Copy `po400` binary to `~/.local/bin/po400` |
| 2 | `chmod +x ~/.local/bin/po400` |
| 3 | Check whether `~/.local/bin` is in `$PATH`; warn with fix instructions if not |
| 4 | Print udev rule instructions (see below) |
| 5 | Print "Installation complete. Run: po400" |

**Uninstall:**
```bash
install.sh --uninstall    # removes ~/.local/bin/po400
```

**Future one-liner:**
```bash
curl -fsSL https://github.com/user/po400/releases/latest/download/install.sh | bash
```

### udev Rule (HID device access without sudo)

`install.sh` cannot write to `/etc/udev/rules.d/` without root.
It prints the following instructions instead:

```bash
# Run once as root:
echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="XXXX", MODE="0666", GROUP="plugdev"' \
  | sudo tee /etc/udev/rules.d/99-po400.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> **TODO**: Replace `XXXX` with actual USB Vendor ID and Product ID
> (confirm via `lsusb` with device attached).

### Rationale: No AppImage

AppImage is a container format designed to wrap standalone binaries so they run on any distro.
Since PyInstaller already produces such a binary, AppImage adds no value and significant tooling
complexity. A transparent `install.sh` is the more honest and widely understood approach for CLI tools.

---

## Windows

### Distribution Artifact

```
po400-setup.exe     ← Inno Setup installer wrapping po400.exe
```

### Installer Framework: Inno Setup

- Produces a single `po400-setup.exe` (double-click, no admin rights for user-local install)
- User-local install path: `%LOCALAPPDATA%\Programs\po400\po400.exe`
- **No command line required.** The Start Menu entry runs `po400.exe` directly; with no
  arguments the binary starts its interactive wizard, so clicking the icon just works.
- Does **not** modify `PATH`, and ships no `cmd`/`doskey` launcher shim. This is a
  deliberate UX decision (psytrap, 2026-10-15), pinned in a comment at the top of
  `packaging/windows/po400.iss`. Adding a PATH entry or a console shim "for
  convenience" means changing the UX decision first, not just the installer.
- Registers uninstaller in "Apps & Features"
- Removes all installed files and registry entries on uninstall

### Start Menu Entry

```
Start Menu
└── PO-400\
    ├── PO-400 Oximeter      ← launches po400.exe in cmd window
    └── Uninstall PO-400     ← Inno built-in uninstaller shortcut
```

### Windows Explorer Context Menu (Right-Click)

Registered under `HKCU` (current user — no UAC required):

| Context | Menu Entry |
|---------|------------|
| Right-click inside a folder (background) | "Open PO-400 here" |
| Right-click on a folder | "Open PO-400 here" |

Both entries launch `po400.exe` (the interactive wizard) for the relevant directory.
No console window is opened for the user to type into.
The entry icon uses the embedded `po400.exe` icon resource (index 0).

Registry keys written by Inno Setup (auto-removed on uninstall):
```
HKCU\SOFTWARE\Classes\Directory\Background\shell\po400\
HKCU\SOFTWARE\Classes\Directory\shell\po400\
```

### Windows Install Result Summary

| Feature | Result |
|---------|--------|
| Apps & Features | "PO-400 Oximeter" with Uninstall button |
| Start Menu | PO-400 → PO-400 Oximeter + Uninstall |
| Explorer right-click | "Open PO-400 here" |
| PATH | Not modified (deliberate -- no command line needed) |
| Admin rights required | No (user-local install) |

### HID Driver (Windows)

If the PO-400 enumerates as a standard HID device, Windows assigns a driver automatically
and `hidapi` works out of the box.
If a vendor-specific driver is assigned, the user must run **Zadig** once to bind WinUSB.
The installer will print instructions for this case.

> **TODO**: Confirm PO-400 USB device class on Windows (check Device Manager).

---

## Icon

A `po400.ico` file is required for:
- PyInstaller binary taskbar icon (Windows)
- Start Menu shortcut icon (Windows)
- Explorer context menu icon (Windows)

> **TODO**: Create or source `po400.ico` and commit to repo before Windows build.

---

## CI/CD Build Pipeline (Future)

GitHub Actions release workflow on tag push:

| Job | Runner | Output |
|-----|--------|--------|
| `build-linux` | `ubuntu-latest` | `po400` (ELF) |
| `build-windows` | `windows-latest` | `po400-setup.exe` (via Inno Setup) |
| `release` | — | Upload both artifacts to GitHub Release alongside `install.sh` |

---

## Open Questions Before POC

1. **USB VID/PID**: What does `lsusb` report for the PO-400? Required for the udev rule.
2. **Windows HID class**: Does the device appear as HID in Device Manager, or does it need Zadig?
3. **Release hosting**: Confirm GitHub Releases as the distribution channel.
4. **Icon**: Design or source a `po400.ico` / `po400.png`.
