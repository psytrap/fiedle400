# T-064: Windows installer UX fixes found during manual install testing

- **Status:** Done
- **Priority:** Medium
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/console.py`, `fiedle400/cli.py` (exit path)
  - `tests/test_console.py`
  - `packaging/windows/fiedle400.iss`

---

## Description & Context

Found 2026-10-21 while psytrap manually ran a fresh installer build on the
real Windows machine (built via `workflow_dispatch` on
`build-release.yml` at current `HEAD`, outside the normal tag-triggered
release flow -- just to get a `fiedle400-setup.exe` to test with):

1. **Console closes before an error can be read.** Double-clicking
   `fiedle400.exe` (or its Start Menu shortcut) with no device connected
   printed `[✗] Error connecting to device: No Pulsox PO-400 device
   found! ...` and the window closed instantly -- Windows destroys a
   console the process owns the moment it exits, so there was no chance
   to read the message. `fiedle400/console.py` already had
   `console_is_owned()`/`enlarge_owned_console()` for exactly this
   double-click-launch scenario (sizing only); it had no exit-side
   counterpart.
2. **Start Menu shortcut said "PO-400 Oximeter", not "fiedle400".**
   Deliberate at the 2026-10-15 po400->fiedle400 rename (see the comment
   still in `fiedle400.iss`: "The device is still the PO-400, so the
   shortcut ... keep[s] that name") -- psytrap now wants the app's own
   name on its own shortcut instead.

---

## Criteria

- [x] On any non-zero exit, if the console is one `fiedle400` owns
      (never one shared with `cmd.exe`/PowerShell), print a short notice
      and pause ~10s before the process actually exits
- [x] Pause logic is off-Windows/shared-console/API-failure safe, same
      rules as `enlarge_owned_console`, and testable without a real delay
- [x] Main Start Menu icon renamed to "fiedle400" (group folder name,
      uninstall shortcut and the `{userdocs}\PO-400` recordings folder
      deliberately left as-is -- not asked for)
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21:** Added `console.pause_before_exit_if_owned(seconds=10, ...)`
to `console.py` (same `console_is_owned` check, mockable `kernel32`/
`platform`/`frozen`/`sleep` params for tests). Wired into `cli.py`'s
`main()`: `run_guarded`'s exit code is checked before `sys.exit`, and the
pause runs only when it's non-zero. 6 new tests added in
`test_console.py` mirroring the existing `TestEnlargeOwnedConsole`
fixture. Full suite: 407 tests, `OK (skipped=7)`.

Renamed the `[Icons]` entry in `fiedle400.iss` from
`{group}\PO-400 Oximeter` to `{group}\fiedle400`.

Not yet re-verified against a freshly rebuilt installer on the real
Windows machine -- the installer psytrap is testing right now predates
both fixes (built before this ticket). Needs another
`workflow_dispatch` build + transfer once ready to re-check.
