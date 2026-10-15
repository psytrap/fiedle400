# Response: open tasks

Written by the cloud side, 2026-10-15, against HEAD `0ab3bf0` (version `0.1.1`,
not bumped). Patches 0005–0009 in order; each is one commit.

| Patch | Task | What it does |
|:---|:---|:---|
| 0005 | psytrap: version info, larger Windows window | `info` prints `po400 Tool Version : 0.1.1 (standalone binary, Windows 8.1, AMD64)`; wizard, `sessions` and `detect` headers show `po400 v0.1.1`; stale `v2.0.0` strings removed. New `po400/console.py` grows the console to 120x40 (3000 lines scrollback) **only when po400 owns it** (Start Menu / double-click). A console shared with cmd or PowerShell is left alone. Only grows, never shrinks; any failure is silent. |
| 0006 | Task 2: Windows live tests | `test_01`/`test_02` skip off Linux with a stated reason; new `test_01b_hid_enumeration` checks VID/PID/path via `hid.enumerate` on every platform; `test_03` uses the `hid` backend and its hidraw-reattach wait is a no-op off Linux. A missing `hid` module skips on Linux and **fails** elsewhere (it is the only backend there). Gating is unit-tested by reloading under a patched `sys.platform`. |
| 0007 | Task 4: `--workdir` / `PO400_WORKDIR` | `po400 download --workdir DIR` beats `PO400_WORKDIR`, which beats the saved setting (or the one-time prompt on a terminal), then the current directory. `-o` still wins over all of them. Neither override prompts or saves; a bad path fails with exit 1 before connecting. The `isatty()` guard is untouched and its tests still pass. README documents it. |
| 0008 | Task 3 + stale plan | G5 now requires `info`/`sessions` on the built artifact, explicitly local-only. G1, G6 (both backends on Linux, `hid` elsewhere), G8, B5, header and workflow line refreshed; B7 recorded. |
| 0009 | — | This file. |

Mock suite after 0008: 157 run, 0 failures, 7 skipped (the live tests).

## Task 1: rename to `fiedle400`

Not started on purpose. It needs psytrap's call on timing (rename after tagging
`v0.1.1`, or before). The cloud's default for the settings question is
**migrate on first run**: copy `po400/config.json` into the new directory if the
new one has none, and leave the old file in place. It will be its own patch,
built on top of 0005–0009.

## Task 5

Nothing done, as the brief says.

## Please verify locally

1. `PO400_LIVE=1 python -m unittest tests.test_device_live -v` on Windows 8.1:
   expect `test_01`/`test_02` skipped with the Linux-only reason and everything
   else passing. Then on Linux with both backends: nothing should change there.
2. Built Windows binary from the Start Menu shortcut: the window should open at
   about 120x40. Run it from an existing cmd window too: that window must keep
   its size.
3. `po400 info` (source and binary) shows the Tool Version line.
4. `po400 download --workdir <dir>` and `PO400_WORKDIR=<dir> po400 download`
   write there without prompting.

## Decisions still open (psytrap)

D1 code signing, D2 macOS, D3 Python floor, D4 minimum Windows in the release
notes. No cloud work depends on them. Suggested release-notes line for the RTC:
"The PO-400 clock reads 2002-07-01 and cannot be set from po400; stored sessions
keep correct timestamps."
