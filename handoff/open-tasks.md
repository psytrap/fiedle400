# Handoff: open tasks

Written by the local side for the cloud, 2026-10-15. Supersedes nothing; the
earlier briefs in this directory are still live and referenced below.

**Repo state:** HEAD `0ab3bf0`, 25 commits on `master`, version `0.1.1`, 130
tests passing (6 skipped — the opt-in live-device tests). No tags exist; nothing
has been released.

## What changed since you last saw this

1. **There is now a GitHub remote:** `https://github.com/psytrap/fiedle400`
   (private). `master` is pushed. The repo is already named `fiedle400` even
   though the code still says `po400` — see task 1.
2. **CI runs for the first time.** `tests.yml` runs on every push and PR across
   ubuntu/windows/macos at Python 3.11; `build-release.yml` builds three
   binaries plus a Windows installer and gates everything behind the tests.
3. **Everything was tested on real Windows hardware.** A Windows 8.1 laptop
   (6.3.9600, AMD64) with the real PO-400 attached, reachable over SSH from the
   local machine. Findings below are measured, not inferred.
4. **Version was bumped to `0.1.1`** (Phase 1 pre-flight, RELEASE_PLAN §1). Do
   not bump again this cycle; fix forward on `0.1.1`.

## Verified — do not redo

- The PO-400 binds to the **stock Windows HID class driver** (`HidUsb`). No
  Zadig, no driver install. Closes the TODOs at PACKAGING.md:137 and :167.
- The **installer works on Windows 8.1**: silent per-user install with no UAC,
  Start Menu shortcut created, and the installed binary reads the live device
  (`info`, `sessions`). So the Server-2022/Python-3.11 build does run on 8.1.
- B6 and B7 are genuinely fixed (B6 had only been half done — README was
  corrected but DESIGN.md and PROTOCOL.md still had seven `file:///home/mik/...`
  links).

---

# Open tasks

## 1. Rename everything to `fiedle400` — the big one

Full surface area and three open questions are written up in **RELEASE_PLAN.md
§3b**. Read that rather than duplicating it here.

Do it as its own change, not mixed with anything else: it touches nearly every
file and will conflict with any patch written against the old paths.

The question that most needs an answer first: **renaming moves the settings
directory** (`%APPDATA%\po400` → `%APPDATA%\fiedle400`), silently abandoning a
stored `workdir`. Either migrate on first run or accept the prompt reappearing.

Also unresolved: renaming *before* tagging `v0.1.1` means the release candidate
that was hardware-tested is not the one that ships.

## 2. Linux-only live tests still fail on Windows

Briefed in full in `handoff/windows-live-tests.md`, with confirmed output
appended. Not yet fixed. Summary:

- `test_01` asserts a `/dev/hidraw` path from a sysfs-only scan → fails
- `test_02` requests the `hidraw` backend, which raises off Linux by design → errors
- `test_03`'s `wait_for_hidraw_reattach()` has no meaning off Linux → fails

Tests 04–06 pass on Windows. The lock needs no change: its `fcntl` import is
already guarded and degrades to a no-op.

## 3. G5 is too weak, and it let a real bug through

The gate runs `dist/po400 --version` and `--help`. A binary that starts fine but
cannot open the device passes it — which is exactly what happened: the first
installer built and ran on the laptop, reported `0.1.1`, and then claimed no
device was present while Windows listed the oximeter and a source install
enumerated it seconds later on the same machine.

Root cause (fixed in `0ab3bf0`): `import hid` happens inside
`hid_driver._get_hid_module()`, and the package ships a compiled extension plus
its hidapi DLL. `po400.spec` named neither, so the frozen build imported the
module but could not call into it.

**The gate still needs rewording** to require a device-touching command on the
built artifact, not just `--version`. Note CI runners have no oximeter, so the
real check can only run locally — G5 should say that explicitly.

## 4. TODO: `--workdir` flag and `PO400_WORKDIR` env var

Recorded in the code at the `target_dir` assignment in `cli.py` and in commit
`bd0b69a`. The new settings system (`po400/config.py`) prompts once
interactively and stores the choice in `%APPDATA%\po400\config.json`. A
non-interactive caller currently has no way to choose a location other than
passing an explicit `-o` per invocation.

Constraint to preserve: the prompt is guarded by `sys.stdin.isatty()`. Any
change must keep that — without it a pipe, a script, CI, or the test suite
blocks forever on `input()`. `tests/test_config.py` asserts `input()` is never
reached when stdin is not a TTY; keep those tests passing.

## 5. The intermittent suite failure was contained, never explained

See `handoff/flaky-suite.md` and your own `flaky-suite-response.md`. Patch 0004
made the live tests opt-in and added a lock, which removed the nondeterminism.
The original one-off failure never reproduced — 30 consecutive live runs clean.

So it is **contained, not diagnosed**. The improved assertions in `test_04` and
`test_06` will name the cause if it recurs. Nothing to do unless it does.

---

# Decisions needed from psytrap (not code tasks)

These were raised in discussion and are still unanswered. They block parts of
the rollout, not the code.

| # | Decision | Why it matters |
|:--|:---|:---|
| D1 | **Code signing** | The installer is unsigned. SmartScreen on Windows 10/11 will warn, and most users read that as malware. This is the main rollout friction and nothing else on the list affects adoption as much. |
| D2 | **macOS** | It is in the build matrix with no test story and no Mac to smoke-test on. Either drop it from the matrix or ship it explicitly marked unsupported. |
| D3 | **Python floor** | `requires-python = ">=3.8"` but CI only tests 3.11. The laptop ran 3.8 fine, but that is one data point. Add 3.8 to the matrix or raise the floor to what is actually tested. |
| D4 | **Minimum supported Windows** | Now partly answered: the build *does* run on 8.1. Still needs stating in the release notes. |

---

# RELEASE_PLAN.md is stale in several places

Worth correcting in the same pass as anything else, since it is the document
the release is run from:

- **Header**: says baseline `0.1.0` and "master has 11 commits"; now `0.1.1` and
  25 commits. Says blockers B1–B6; B7 (console encoding) also exists and is fixed.
- **Workflow line**: says psytrap pulls changes locally — there is a git remote now.
- **G1**: says "102 pass / 6 skip"; now 130 tests.
- **G5**: says "Not yet verified"; the binary and installer are now verified on
  real hardware. See task 3 for the rewording it needs.
- **G6**: the Windows criterion ("`po400 info` runs on a real machine") now
  passes. The "both backends" wording is Linux-only — on Windows the `hidraw`
  backend raises by design, so it should read: both backends on Linux, `hid`
  only elsewhere.
- **G8**: described as a behaviour violation. It was not — the code always wrote
  to the cwd; only the help strings claimed `output/`. Fixed in `9647913`.
  The gate text should say what it now checks.
- **B5**: mentions `po400.egg-info` debris; untracked, not an issue in git.

---

# Constraints

- **Never erase device flash.** No `po400 clear`, no format. The stored session
  (214 records, 2026-09-30) is real data.
- The local machine is Linux; the cloud has no device. Anything needing the
  oximeter or Windows has to come back here to be run. Ask and the output will
  be returned through this directory.
- Device RTC reads `2002-07-01` and **cannot be set** — psytrap reports the
  set-time command is unsupported by this firmware. Stored sessions carry
  correct timestamps regardless, so this appears cosmetic, but it is worth a
  line in the release notes.
