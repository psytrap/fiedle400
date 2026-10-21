# T-063: `pyproject.toml` declares the wrong `hid`-family package

- **Status:** Done
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `pyproject.toml` (`dependencies`, `[project.optional-dependencies].dev`)
  - `.github/workflows/build-release.yml:46` (`pip install pyinstaller hidapi`)
  - `fiedle400.spec` (its comment assumes the bundled-binary package)
  - `fiedle400/hid_driver.py` (`import hid`)

---

## Description & Context

Found 2026-10-21 setting up a clean Windows dev environment for T-047's
G5/G6 (fresh Python 3.11 venv, `pip install -e . pyinstaller`, then
`pyinstaller fiedle400.spec`): the frozen `dist\fiedle400.exe` failed
every device command with:

```
Error connecting: The 'hid' library is required for the 'hid' backend but is not installed.
Install it with: pip install hid
```

...despite `pip install -e .` having installed something importable as
`hid` moments earlier. Root cause: **there are two unrelated PyPI packages
that both install a top-level module literally named `hid`:**

- **`hid`** (the one `pyproject.toml` actually names, `dependencies = ["hid; sys_platform == 'win32' or sys_platform == 'darwin'"]`):
  a thin ctypes wrapper. Its `__init__.py` (confirmed by inspection,
  version 1.0.9) calls `ctypes.cdll.LoadLibrary('hidapi.dll')` --
  it does **not** bundle that DLL itself. `site-packages/hid/` on a fresh
  install contains only `__init__.py`, no binary.
- **`hidapi`** (what `.github/workflows/build-release.yml:46` *actually*
  installs: `pip install pyinstaller hidapi`): a different package that
  also exposes `import hid`, but ships a compiled extension with the
  hidapi backend built in -- no system DLL needed. This is almost
  certainly what `fiedle400.spec`'s comment describes ("the package ships
  a compiled extension plus its hidapi DLL").

So the **real release build never actually exercises `pyproject.toml`'s
declared dependency at all** -- CI installs `hidapi` directly, bypassing
`pip install -e .`/`pyproject.toml` entirely, which is why this has never
broken a release. But anyone (a new contributor, or this session) who sets
up a dev environment the normal way -- `pip install -e .` or `pip install
-e .[dev]` -- gets the broken, DLL-less `hid` package instead, and a
PyInstaller build from that environment produces a binary that cannot
talk to any device on Windows (or macOS, same dependency line) at all.

**Confirmed only on Windows this session** (no macOS hardware available);
the `sys_platform == 'darwin'` line in the same dependency almost
certainly has the identical problem, unverified.

---

## Criteria

- [x] `pyproject.toml`'s `dependencies` (and the `dev` optional group)
      changed from `"hid"` to `"hidapi"` for `win32`/`darwin`, so
      `pip install -e .` matches what CI actually ships
- [x] `fiedle400.spec`'s `collect_dynamic_libs('hid')` re-verified against
      the corrected package (it imports by module name `hid` either way,
      so this likely needs no change, but confirm it actually collects a
      binary now where it silently collected zero before)
- [x] A built binary from a clean `pip install -e .` venv (not a
      hand-patched one) connects to a real device on Windows
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21:** Changed `pyproject.toml`'s `dependencies` and `dev` extra
from `"hid"` to `"hidapi"`. Also updated the user-facing error message in
`fiedle400/hid_driver.py:_get_hid_module` (previously told users to
`pip install hid` -- the exact wrong package that caused this whole
investigation) to say `pip install hidapi`, with a one-line pointer to
this ticket.

Verified on the real Windows machine (`192.168.2.165`): uninstalled both
`hidapi` and `fiedle400` from the venv, ran a genuinely clean
`pip install -e .` -- confirmed it now pulls `hidapi-0.15.0` (the
compiled-extension package), not the ctypes `hid` package. Rebuilt with
`pyinstaller fiedle400.spec` and re-ran `dist\fiedle400.exe info` against
the real device: connects and reads device info correctly. This is the
same build/verify pass that produced T-047's G5/G6 Windows results.

The `collect_dynamic_libs('hid')` warning in `fiedle400.spec`
("skipping library collection for module 'hid' as it is not a package")
still prints on every build, both before and after this fix -- harmless
(PyInstaller's normal binary-dependency analysis already bundles the
single-file `.pyd` extension correctly, confirmed by the binary actually
working), but the spec's comment claiming the package "ships a compiled
extension plus its hidapi DLL" doesn't quite match this single-`.pyd`-file
layout. Left as a cosmetic note, not worth its own ticket.
