# T-040: tkinter wizard, with the terminal wizard as fallback

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Cloud (implementation), Local (Windows look, binary size)
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (`run_interactive_wizard`, `main`'s no-argument path)
  - new `fiedle400/wizard.py` (controller, no tkinter import) and
    `fiedle400/wizard_gui.py` (ttk front-end, imported lazily)
  - `fiedle400/engine/device.py` (`download_session`: optional progress callback)
  - `scripts/wizard_gui_mockup.py`, `tests/test_wizard_gui_mockup.py` (T-033's mockup; drop or
    replace once the real GUI exists)
  - `tests/test_cli_interactive.py`, `.github/workflows/tests.yml`, `fiedle400.spec`,
    `README.md`

---

## Description & Context

Follow-up to [T-033](../done/2026-W43/T-033-migrate-wizard-to-tkinter.md), which recommends
how to do and test it. In short:
- Extract the wizard's flow into `fiedle400/wizard.py`, tested with plain `unittest` and the
  mocked engine.
- Make the terminal wizard and a ttk GUI two thin front-ends over it.
- Have `fiedle400` with no arguments start the GUI when tkinter and a display are available,
  and fall back to the terminal wizard otherwise; `--gui` and `--tui` force either one.
- Run the downloads in a worker thread and pass results to Tk through a queue.
- GUI smoke tests skip without a display; CI runs them on Ubuntu under `xvfb-run -a`.

The screens follow `scripts/wizard_gui_mockup.py` (screenshots in the project files under
`po400-t033/`), adjusted to psytrap's feedback.

**Decided (psytrap, 2026-10-21):** the erase default stays as today, `[Y/n]` (default yes).
The GUI's erase confirmation follows it: its default button is "Erase", not the mockup's
"Keep recordings".

**Open questions (psytrap):**
1. Keep `console=True` (a console window next to the GUI on Windows), since the same exe is
   the CLI?
2. Any changes to the mockup screens.

---

## Criteria

- [ ] `fiedle400/wizard.py` holds the flow, with no tkinter import. The terminal wizard runs
      on it, and the behaviour that `tests/test_cli_interactive.py` covers is unchanged
      (except where psytrap decides otherwise above).
- [ ] `fiedle400/wizard_gui.py` (ttk) implements the agreed screens. Downloads run off the
      Tk thread, with progress per recording and overall.
- [ ] GUI or terminal wizard is picked automatically, with `--gui` and `--tui` flags. No
      tkinter or no display falls back to the terminal wizard with a one-line note, never
      a traceback.
- [ ] Controller tests run everywhere. GUI smoke tests skip without a display.
      `tests.yml` runs them under `xvfb-run -a` on Ubuntu; whether they run or skip on the
      Windows and macOS runners is recorded.
- [ ] README updated.
- [ ] Local (psytrap), not exercised in the cloud: the binary on Windows (look, console
      window, a real download and erase with the device) and the binary size compared
      with 0.4.27.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
