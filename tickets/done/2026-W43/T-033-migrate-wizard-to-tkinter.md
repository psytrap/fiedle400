# T-033: Evaluate migrating the interactive wizard from a terminal TUI to tkinter

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (the interactive wizard: device pick, format menu,
    the `[y/N]` "Open it in the HTML viewer now?" prompt, and everything
    else driven by `input()`)
  - `.github/workflows/tests.yml` (headless runner -- no display, no
    `DISPLAY`, no browser)
  - `tests/test_cli_graceful.py`, and whatever other `tests/test_cli_*.py`
    file actually covers the wizard today -- grep before assuming which
  - `README.md` (wizard usage)

---

## Description & Context

psytrap: the terminal-prompt wizard in `fiedle400/cli.py` is to be replaced
with a `tkinter`-based GUI -- standard library only, no Qt or other
third-party toolkit. This is scoped strictly to the wizard's own
interaction (device pick, format choice, confirmations); it does not touch
`fiedle400/spo2_viewer.py` or the HTML viewer in any way.

This is an evaluation ticket, same shape as T-007/T-009: it exists to work
out *how* the migration would be tested, not to carry out the migration
itself in this ticket.

**The open question is test strategy**, since the wizard today is
exercised in CI with no display and no real terminal interaction beyond
mocked `input()`/`builtins.input`. A tkinter GUI changes that shape:

- Can the decision logic (which device, which format, what gets passed to
  `download()`) be separated from widget code cleanly enough to keep
  testing it with plain `unittest`, independent of any `Tk` instance?
- Can the GUI layer itself (window construction, widget wiring, event
  bindings) run under CI at all -- e.g. `xvfb-run` on the GitHub Actions
  Ubuntu runner -- or does it stay untested in CI and rely on local/manual
  verification instead?
- What should happen with no display available (SSH, CI, headless) or
  when `tkinter`/`python3-tk` isn't installed (some distros ship it as a
  separate OS package) -- evaluate whether a fallback is needed, without
  committing to one here.
- "tkinter" covers two widget sets in the stdlib: the classic `tkinter`
  widgets (`tk.Button`, `tk.Entry`, ...) and `tkinter.ttk`, the themed set
  (`ttk.Button`, `ttk.Combobox`, `ttk.Progressbar`, ...) that looks native
  per-OS and is the generally preferred choice for new UIs. Both are
  stdlib-only, so "no third-party toolkit" permits either -- the
  evaluation should say whether `ttk` is assumed for the actual widgets,
  since that choice affects what the CI test-strategy recommendation is
  even testing (widget classes differ, though the headless/`xvfb-run`
  question is the same for both).

---

## Criteria

- [x] A written recommendation for the test strategy: how wizard decision
      logic would be tested independent of tkinter, and whether/how the
      GUI layer itself gets CI coverage (e.g. `xvfb-run`) versus staying
      manually verified -- with a reason, not a flat yes/no.
- [x] The no-display / missing-`python3-tk` question is addressed in the
      recommendation (even if the answer is "out of scope, needs its own
      ticket").
- [x] The recommendation states whether `tkinter.ttk` (themed widgets) or
      plain `tkinter` widgets is assumed for the migration, with a reason.
- [x] Any recommended implementation approach is filed as its own
      follow-up ticket rather than carried out inline here.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud, patch 0030). Evaluation only; the migration is
[T-040](../../open/T-040-tkinter-wizard.md).

**Proposal, as a clickable mockup.** `scripts/wizard_gui_mockup.py` (stdlib, made-up data, no
device, writes nothing) shows the proposed screens. You can also open any one of them
directly with `--screen device|nodevice|save|progress|done|erase`:
- **device:** device details and the recordings table, all selected. Buttons: Download, Erase,
  Quit.
- **nodevice:** what to check, with a Retry button.
- **save:** the format as radio buttons (HTML default), the file name and Browse. The system
  Save dialog does the overwrite question.
- **progress:** a progress bar per recording and one overall.
- **done:** the saved path, with Open in browser and Show in folder. Never opens anything by
  itself.
- **erase:** a confirmation whose default button is "Keep recordings".

Screenshots (Linux/X11, `clam` theme, rendered headless under Xvfb) are in the project files
under `po400-t033/`, not in the repo. Run the script on Windows to see the native look. It maps
one-to-one onto today's terminal flow: menu, selection, format, file name, overwrite, download,
open?, erase?, back to menu.

**Recommendation: test strategy.**
1. *Decision logic without tkinter.* Move the flow out of `run_interactive_wizard` into a
   small controller module, `fiedle400/wizard.py`, which never imports tkinter. It does:
   - connect, list recordings, and parse a selection (`parse_session_selection`);
   - the format choice (`EXPORT_FORMATS`, default html);
   - the default name and overwrite suggestion (`generate_iso_filename`,
     `get_next_available_filename`);
   - the download (with a progress callback) and the erase.

   The terminal wizard and the GUI become two thin front-ends over it. The controller is tested
   with plain `unittest` and the mocked engine and device, as `tests/test_cli_interactive.py`
   already does. That runs on all three CI OSes with no display. Nearly all the risk (which
   recordings, which format, which file, whether the device gets erased) sits here, so this is
   where the coverage goes.
2. *GUI layer: smoke tests, skipped without a display.* Build each screen with a fake
   controller, then check that the widgets exist and that `Button.invoke()` calls the right
   controller method. `tests/test_wizard_gui_mockup.py` shows the pattern on the mockup. It
   skips (does not fail) when tkinter or a display is missing, so the T-009 constraint holds:
   nothing needs a display to pass CI. To actually run these tests in CI, prefix the Ubuntu
   test step with `xvfb-run -a` (Xvfb ships on the GitHub Ubuntu image). setup-python's builds
   include tkinter on all three OSes. Whether Tk opens a window on the Windows and macOS
   runners is expected but unverified; T-040 checks it, and a missing display only means a skip.
   No pixel or screenshot tests: the look is checked by hand, locally, on Windows.
3. *Threading.* HID reads block, so the download runs in a worker thread and reports through a
   `queue.Queue` that the Tk main loop polls with `after()`. Tk is touched only from the main
   thread. The tests call the controller synchronously, so they need no threads or timing.
   `engine.download_session` has no progress hook today; T-040 adds an optional callback.

Verified here: the mockup tests pass under Xvfb with Python 3.12 + python3-tk (5 tests), and
they skip under the cloud's default Python 3.13, which has no tkinter.

**No display / no python3-tk.** Keep the terminal wizard as the fallback, not as dead code: it
costs little once both front-ends share `wizard.py`. Running `fiedle400` with no arguments
starts the GUI when `import tkinter` works and `tk.Tk()` succeeds. Otherwise it prints a
one-line note ("no display / tkinter not installed, using the terminal wizard") and runs the
terminal wizard. `--gui` and `--tui` force either one (`--gui` fails gracefully, with no
traceback, per the release rules). Where each case comes up:
- Missing python3-tk only affects pip installs on Debian, Ubuntu and Fedora, which split it out.
- The PyInstaller binary bundles Tcl/Tk when the build machine's Python has it, which the
  python.org and setup-python builds do.
- Costs for T-040 to measure locally: Tcl/Tk adds a few MB to the binary, which eats part of
  T-006's matplotlib saving. Also, `console=True` in `fiedle400.spec` keeps a console window
  next to the GUI on Windows. Keep it, since the same exe is the CLI; a second, windowed exe
  is not worth it for this project.

**ttk, not classic tk widgets.** Use `tkinter.ttk` for every widget; only `Tk` and `Toplevel`
come from classic tkinter. The reasons:
- ttk uses the native theme on Windows (`vista`) and macOS (`aqua`). Classic widgets look like
  1990s Motif there.
- The two widgets this wizard needs most, the recordings table (`ttk.Treeview`) and the
  progress bar (`ttk.Progressbar`), exist only in ttk.
- The headless and `xvfb-run` story is identical for both, so the choice does not change the
  test strategy. On Linux the mockup picks `clam`, because the stock `default` theme looks dated.

**Open questions for psytrap (in T-040):**
- The terminal wizard's erase prompt defaults to Yes (`[Y/n]`). The mockup instead offers an
  "Erase device memory…" button whose confirmation defaults to No. Which do you want for the GUI?
- Keep the console window on Windows?
