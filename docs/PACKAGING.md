# fiedle400 — Packaging & Distribution

How the release artifacts are built. The build is `.github/workflows/build-release.yml`
(runs on `v*` tags and manually); `tests.yml` must pass first. Version numbers and when
to bump them: [RELEASE_PLAN.md](RELEASE_PLAN.md).

## Principle

`fiedle400` ships as a **self-contained binary** built with PyInstaller from
`fiedle400.spec`; no Python is needed on the user's machine. PyInstaller cannot
cross-compile, so CI builds one binary per OS. The binary no longer bundles `matplotlib` (T-006:
`plot` was replaced by the stdlib-only `view`; RELEASE_PLAN B1b has the size history, about 35 MB less). The workflow smoke-tests every
binary (`--version`, `--help`, `config`).

| Artifact | Built on | Contents |
|---|---|---|
| `fiedle400-linux-x64.tar.gz` | ubuntu-22.04 (pinned, glibc 2.35: 22.04 LTS is the minimum supported Linux; T-049) | binary, `install.sh`, `fiedle400_setup-udev.sh` |
| `fiedle400-windows-x64.exe` | windows | portable binary |
| `fiedle400-setup.exe` | windows | Inno Setup installer around the exe |
| `fiedle400-macos-arm64` | macos | binary (Apple Silicon); verified by CI only, no Mac hardware test. CI also marks the packaged asset quarantined and runs it after the README's `chmod +x` / `xattr -d` steps (T-049) |

Binaries are unsigned (RELEASE_PLAN D1); the release notes explain SmartScreen.

## Linux

- `install.sh` copies the binary to `~/.local/bin` and warns if that is not on `PATH`.
  `install.sh --uninstall` removes it and asks before removing the saved settings.
- Device access needs a one-time root step: `sudo ./fiedle400_setup-udev.sh`. It writes
  the `99-pulsox*.rules` files in `/etc/udev/rules.d/` (USB `28e9:028a`) and nothing else.
  Verify afterwards with `fiedle400 selftest`.
- Minimum: Ubuntu 22.04 LTS (psytrap, 2026-11-02). CI builds on `ubuntu-22.04` and runs the
  packaged asset in a clean `ubuntu:22.04` container (`--version`, `--help`, `config`; T-050).
- No AppImage: the PyInstaller binary already runs on any distro, so AppImage adds nothing.

## Windows

Source: `packaging/windows/fiedle400.iss`, built by CI with `/DAppVersion=<__version__>`.

- Per-user install to `%LOCALAPPDATA%\Programs\fiedle400`; no admin rights.
- Start Menu entry runs `fiedle400.exe`; with no arguments it opens the interactive wizard.
- Explorer right-click entries ("Open fiedle400 here", on folders and folder backgrounds) under
  `HKCU\SOFTWARE\Classes\Directory\{Background\,}shell\fiedle400`; removed on uninstall.
- Creates `Documents\fiedle400` as the default working folder for the shortcut (T-064;
  must match `fiedle400/config.py`'s `default_workdir()`).
- **PATH is deliberately not modified** and no command-line shim is shipped (UX decision,
  2026-10-15, pinned in a comment at the top of the `.iss`). Changing that means
  changing the decision first.
- No driver step: the device enumerates as a standard HID device and `hidapi` works
  out of the box (verified on Windows 8.1, RELEASE_PLAN D4).
- Ships a synthetic demo recording (`demo.SpO2`, no real device data, T-055) into
  `Documents\fiedle400` on first install, plus a "View Demo Recording" Start Menu entry
  (`fiedle400.exe view demo.SpO2`) -- lets a new user see the viewer without a device.
  Regenerate with `scripts/make_demo_recording.py` if it ever needs to change.
- English-only installer UI (T-065).
- CI first installs the latest published release, runs this build's installer over it and checks
  version, uninstall entry, files, Start Menu group, context-menu keys and that the user's files
  in `Documents\fiedle400` survive; then uninstalls and checks nothing is left (T-097). After
  that it installs fresh, checks the exe, folder and `--version`, and uninstalls.
- Known limit (T-097): `UsePreviousAppDir=no` (needed for the po400 rename) means an upgrade
  always installs to the default folder. Someone who picked a custom folder gets the new
  version in the default one and an orphaned old copy in theirs.

## Checklist when changing packaging

1. Build locally or let CI build; the smoke tests are the gate.
2. If a user-visible path or name changes, update the `.iss`, `install.sh`, the release
   notes in `build-release.yml` and README together.
3. Keep `fiedle400.spec` hidden imports in line with new modules.
