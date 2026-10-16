# fiedle400 — Packaging & Distribution

How the release artifacts are built. The build is `.github/workflows/build-release.yml`
(runs on `v*` tags and manually); `tests.yml` must pass first. Version numbers and when
to bump them: [RELEASE_PLAN.md](RELEASE_PLAN.md).

## Principle

`fiedle400` ships as a **self-contained binary** built with PyInstaller from
`fiedle400.spec`; no Python is needed on the user's machine. PyInstaller cannot
cross-compile, so CI builds one binary per OS. `matplotlib` is bundled so that `plot`
works (+35 MB, decision recorded in RELEASE_PLAN B1b). The workflow smoke-tests every
binary (`--version`, `--help`, `config`).

| Artifact | Built on | Contents |
|---|---|---|
| `fiedle400-linux-x64.tar.gz` | ubuntu | binary, `install.sh`, `fiedle400_setup-udev.sh` |
| `fiedle400-windows-x64.exe` | windows | portable binary |
| `fiedle400-setup.exe` | windows | Inno Setup installer around the exe |
| `fiedle400-macos-arm64` | macos | binary (Apple Silicon); verified by CI only, no Mac hardware test |

Binaries are unsigned (RELEASE_PLAN D1); the release notes explain SmartScreen.

## Linux

- `install.sh` copies the binary to `~/.local/bin` and warns if that is not on `PATH`.
  `install.sh --uninstall` removes it.
- Device access needs a one-time root step: `sudo ./fiedle400_setup-udev.sh`. It writes
  the `99-pulsox*.rules` files in `/etc/udev/rules.d/` (USB `28e9:028a`) and nothing else.
  Verify afterwards with `fiedle400 selftest`.
- No AppImage: the PyInstaller binary already runs on any distro, so AppImage adds nothing.

## Windows

Source: `packaging/windows/fiedle400.iss`, built by CI with `/DAppVersion=<__version__>`.

- Per-user install to `%LOCALAPPDATA%\Programs\fiedle400`; no admin rights.
- Start Menu entry runs `fiedle400.exe`; with no arguments it opens the interactive wizard.
- Explorer right-click entries ("Open PO-400 here", on folders and folder backgrounds) under
  `HKCU\SOFTWARE\Classes\Directory\{Background\,}shell\fiedle400`; removed on uninstall.
- Creates `Documents\PO-400` as the default working folder for the shortcut.
- **PATH is deliberately not modified** and no command-line shim is shipped (UX decision,
  2026-10-15, pinned in a comment at the top of the `.iss`). Changing that means
  changing the decision first.
- No driver step: the device enumerates as a standard HID device and `hidapi` works
  out of the box (verified on Windows 8.1, RELEASE_PLAN D4).
- CI installs the installer silently, checks the exe, folder and `--version`, then uninstalls.

## Checklist when changing packaging

1. Build locally or let CI build; the smoke tests are the gate.
2. If a user-visible path or name changes, update the `.iss`, `install.sh`, the release
   notes in `build-release.yml` and README together.
3. Keep `fiedle400.spec` hidden imports in line with new modules.
