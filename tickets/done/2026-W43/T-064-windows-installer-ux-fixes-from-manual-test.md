# T-064: Windows installer UX fixes found during manual install testing

- **Status:** Done
- **Priority:** Medium
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/console.py`, `fiedle400/cli.py` (exit path, `_open_in_viewer`)
  - `fiedle400/config.py` (`default_workdir`)
  - `tests/__init__.py`, `tests/test_console.py`, `tests/test_cli_graceful.py`
  - `packaging/windows/fiedle400.iss`
  - `PACKAGING.md`

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
   name on its own shortcut instead. Follow-up: the recordings/output
   folder (`{userdocs}\PO-400`, also set as `config.py`'s
   `default_workdir()` for Windows) got the same treatment, renamed to
   `fiedle400` -- both files have to move together or the shortcut's
   working directory and the saved-settings default would disagree.
3. **"Open it in your browser now?" failed with "Could not open a
   browser".** Root cause (confirmed live via SSH on the same Windows
   8.1 machine): `assoc .html` reported no file-extension association at
   all, even though `ftype htmlfile` showed Internet Explorer registered
   -- so every `os.startfile(path)` call raised and `_open_in_viewer`
   correctly fell back to printing the saved-file path. Restoring the
   association by hand (`assoc .html=htmlfile`, no admin needed) fixed
   this one machine, but psytrap asked for the same fix pattern already
   used on Linux (`_resolve_linux_browser_argv`, resolving the actual
   default *browser* rather than trusting a possibly-missing/drifted
   file-type association) to apply on Windows too, so a similarly broken
   machine doesn't need a manual `assoc` fix again.

---

## Criteria

- [x] On any non-zero exit, print a short notice and pause ~10s before the
      process actually exits -- on every platform, not only when Windows
      reports an owned console (psytrap, 2026-10-21; supersedes the
      narrower Windows-owned-console-only scope this criterion started
      with)
- [x] Pause logic never blocks the automated test suite for real, and is
      testable without a real delay
- [x] All remaining "PO-400" mentions in the installer renamed to
      "fiedle400": app name/version string, uninstall display name, group
      folder, uninstall shortcut, Explorer context-menu text (psytrap
      asked for this after seeing them still in the rebuilt installer --
      supersedes the narrower initial scope)
- [x] Recordings/output folder and `config.py`'s matching
      `default_workdir()` renamed from `PO-400` to `fiedle400` together
- [x] Windows resolves the real default browser via the registry
      (`http`'s `UserChoice` association) before falling back to
      `os.startfile`, mirroring the existing Linux `xdg-settings` logic
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

Renamed `{userdocs}\PO-400` to `{userdocs}\fiedle400` throughout
`fiedle400.iss` ([Dirs], [Files], both [Icons] entries' `WorkingDir`/
`Parameters`) and `config.py:default_workdir()` to match; updated
`PACKAGING.md`'s description of both. psytrap's existing
`Documents\PO-400` folder on the test machine (created by the installer
run earlier this session) is now orphaned from the new default -- not
migrated automatically, since it only affects this one pre-fix test
install.

Added `_resolve_windows_browser_argv()` to `cli.py`: reads
`HKEY_CURRENT_USER\...\UrlAssociations\http\UserChoice`'s `ProgId`, then
that ProgId's `shell\open\command` under `HKEY_CLASSES_ROOT`, parses it
with `shlex.split(..., posix=False)` (keeps backslashes intact for
Windows paths) and substitutes `%1` with the real path. `_open_in_viewer`
tries this first on Windows, falling back to `os.startfile` if
resolution or launch fails -- same two-tier structure as the Linux path.
3 new tests in `test_cli_graceful.py::TestOpenInViewer` (a fake `winreg`
module injected via `sys.modules`, mirroring the existing Linux tests'
`subprocess.run` mocking). Full suite: 409 tests, `OK (skipped=7)`.

Separately, restored the real Windows 8.1 test machine's broken `.html`
association directly (`assoc .html=htmlfile`) so it could keep testing
in the meantime -- that was a one-off fix to the machine, not something
this code change depends on.

First `workflow_dispatch` re-build (run 39603457237) caught a miss: the
installer job's own smoke test in `build-release.yml` still hardcoded
the old `\PO-400` data-folder path, so it failed on the folder rename
(`throw "data folder was not created at ...\PO-400"`) before an installer
artifact was even produced. Fixed the one remaining reference (line 180)
to `\fiedle400`; the other `PO-400` mentions in that file are release-note
prose about the device itself and are correctly left alone.

psytrap tested the rebuilt (0.4.35) installer and found several more
"PO-400" mentions still visible: the wizard's `AppName`/`AppVerName`
("fiedle400 (PO-400 Oximeter)"), `DefaultGroupName` (Start Menu group
folder), `UninstallDisplayName`, the "Uninstall PO-400" shortcut, and
the Explorer context-menu task description/label ("Open PO-400 ...").
These were deliberately left alone in the first pass (noted above as
"not asked for"), but psytrap now wants the app's own name everywhere,
superseding that narrower scope. Renamed all of them to "fiedle400" in
`fiedle400.iss` and the matching description in `PACKAGING.md`. Left
`AppId` (GUID, must stay stable across versions) and the historical
rename-comment prose referring to the device by its real name unchanged.

Rebuilt (0.4.36) installer transferred and tested by psytrap: installer
naming confirmed clean ("looks good finally"). Verified `info` against the
real device post-install (exit 0, correct hardware readout) and that
`Documents\fiedle400` holds the expected recordings/exports.

psytrap then asked whether the error-exit pause applies on Linux too --
it didn't (Windows-only, by original design, since only Windows destroys
an owned console on exit) -- and, after confirming that, asked for it on
every platform regardless, including scripted/CI invocations. Rewrote
`pause_before_exit_if_owned()`: dropped the Windows/owned-console check
entirely (removed `kernel32`/`platform`/`frozen` params, `console_is_owned`
is no longer called from here), so it now always prints the notice and
sleeps `seconds` before `cli.main()` exits non-zero, on any platform.

This broke the test suite badly on the first attempt: many tests call
`cli.main()` directly in-process and exercise error exits, so the suite
went from ~8s to over 2 minutes (409 tests each hitting a real
`time.sleep(10)`). First fix attempt detected "the test suite itself is
running" via `"unittest" in sys.modules` plus `sleep is time.sleep`
identity, which mostly worked but missed four tests in
`test_recording.py::TestViewCommand` that mock `fiedle400.cli.time.sleep`
for an unrelated reason (silencing a different internal sleep) --
`console.py`'s own default argument had already captured the *original*
`time.sleep` object before that patch ran, so the identity check saw a
mismatch and let the real sleep through anyway (4 x 10s, exactly the
remaining gap). Replaced the detection with an explicit
`RUNNING_FIEDLE400_TESTS` env var set unconditionally in `tests/__init__.py`
(deliberately not prefixed `FIEDLE400_`, since `tests/hwsim.py`'s
`scrub_env()` wipes that whole prefix for isolation and would have undone
it mid-test). Suite is back to 406 tests in ~8s. `test_console.py`'s
`TestPauseBeforeExitIfOwned` rewritten for the new unconditional-everywhere
behaviour (was: 6 tests of the owned-console logic; now: confirms the
test-suite skip, and that it pauses/respects a custom duration once that
env var is removed).

psytrap then ran a full manual download test with the installed 0.4.37
app on the real Windows machine (recording download end-to-end through
the installed binary, not over SSH) and confirmed it all good: the
session downloaded cleanly, opened in the resolved default browser
automatically, and landed in `Documents\fiedle400` as expected. All four
findings from this ticket are now verified against a real install.
