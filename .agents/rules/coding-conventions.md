# Rule: Coding Conventions

## Trigger
- When writing or reviewing code in `fiedle400/`, `tests/` or `scripts/`.
- Cite it in a review the way `code-review-standards.md` is cited.

## Names
A name says what the value is, in this project's words: `descent_start`, `nadir_index`,
`serial_number`, not `st`, `en`, `sn`. The reader should not have to keep a private
glossary in their head (T-043: `desaturation.py` once used `st`/`en`/`v`/`p`/`cur`/`n`/`c`
in one function, which made the algorithm unreadable).

Short names are fine only in these cases:
- **Loop indices** `i`, `j`, `k` over integer ranges.
- **Python's own conventions:** `self`, `cls`, `args`, `kwargs`, `argv`, `_` for an ignored value.
- **Names that copy an outside source:** a field named the way `PROTOCOL.md`, a struct, an
  API or a cited formula names it (`m0`..`m2` mask bytes, termios `cc`/`iflag`, Win32 `DCB`,
  `DWORD`, `b0`..`b3` for the documented byte positions, the `eb`/`ec`/`ed` opcodes). Point at
  the source in a comment if it is not obvious.
- **Acronyms that are the normal word:** `spo2`, `ppg`, `rtc`, `hid`, `usb`, `vid`/`pid`, `crc`,
  `csv`, `json`, `html`, `iso`, `tty`, `sysfs`, `js` (JavaScript), `py` (Python).

Everything else is spelled out, including comprehension variables and "obvious" ones:
`session`, not `s` or `sess`; `device`, not `dev`; `heart_rate`, not `hr`; `error`, not `e`;
`timestamp`, not `ts`. (T-106 applied this to `fiedle400/`, `tests/`, the viewer's JavaScript
and HTML element ids, 2026-11-02.)

The rule covers the viewer's JavaScript (camelCase: `formatSeconds`, `plotWidth`,
`EVENT_MAX_TIME`), its HTML element ids, and the keys fiedle400 writes itself: CSV/JSON
columns, the viewer's analysis keys (`sequence`, `from_percent`, `index_per_hour`,
`average_event_duration_seconds`). Keys that come from outside keep their spelling: hidapi's
`manufacturer_string`, third-party CSV columns such as `pr`, and the `expected.json` keys
that `scripts/check_spo2_assistant_report.py` reads from probe files already recorded.

## What this file does not cover
- Naming *consistency* across files: `code-review-standards.md` ("Clean code").
- Tests, pyflakes, the definition of done, delivery and versions: `AGENTS.md`.
- Line length, type hints, docstring shape, comment policy: not decided. Match the
  surrounding code until a rule is written here.
- `scripts/`: not renamed yet; new code there follows the rule.
