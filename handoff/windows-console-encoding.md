# Delegation brief: CLI crashes on Windows consoles with a legacy codepage

Product-code bug, found on real hardware. Cloud's to fix.

## Symptom

On the Windows 8.1 laptop, `py -3.8 -m po400 info` connects to the device,
prints three lines correctly, then dies:

    Connected to \\?\HID#VID_28E9&PID_028A#...!
    ==================================================
      PULSOX PO-400 DEVICE & HARDWARE INFORMATION
    ==================================================
      Device Path / Node     : \\?\HID#VID_28E9&PID_028A#...
      Active HID Backend     : hid (cross-platform)
      Hardware Model         : GigaDevice MCU HID Oximeter (CMS-60D v2 / Pulsox PO-400)
    \u274c po400 0.1.0: unexpected error: UnicodeEncodeError: 'charmap' codec
       can't encode characters in position 2-3: character maps to <undefined>

Note the failure is self-demonstrating: the graceful-error handler tries to
print its own `❌` and that is the character it cannot encode.

## Root cause, confirmed

- Console codepage is **850** (`chcp` reports "Aktive Codepage: 850") on this
  German Windows. cp850 cannot encode `❌` or the box-drawing `└─`.
- `po400/cli.py` contains **28 non-ASCII characters** (`❌ ⚠ ✅ ✓ ✗ 📊 🔍 🕒 └ ─ —`)
  and `po400/plot.py` another 5.
- There is **no encoding handling anywhere** in the codebase: grep for
  `encoding|reconfigure|PYTHONIOENCODING|chcp|utf-8` in `po400/cli.py` returns
  nothing.

Proof of cause: the identical command with `PYTHONIOENCODING=utf-8` set prints
the complete report with no error, including every box-drawing character.

## Not Windows-8-specific

Any Windows console on a legacy codepage hits this -- `cmd.exe` on Windows 10
and 11 included. Windows Terminal on 11 defaults to UTF-8 and would mask it,
so it must not be dismissed as an old-OS artifact. German, French and other
non-English installs are the most exposed, since they default to cp850/cp1252.

## The fix wanted

Make output encoding-safe at startup, e.g.

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

guarded for Python versions without `reconfigure`, plus an ASCII fallback for
the symbols when the console genuinely cannot do UTF-8.

**Do not fix this by stripping the emoji and box-drawing characters.** That
would permanently degrade output everywhere it currently works (Linux, macOS,
Windows Terminal) to accommodate one legacy console. The symbols should survive
where they can be rendered.

Apply the same treatment to `po400/plot.py`.

## Environment

Windows 8.1 (6.3.9600) AMD64, Python 3.8 32-bit, `hidapi` 0.15.0 (cp38-win32
wheel from PyPI), console codepage 850, real PO-400 attached and working.
