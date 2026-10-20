# T-033: Evaluate migrating the interactive wizard from a terminal TUI to tkinter

- **Status:** Open
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

---

## Criteria

- [ ] A written recommendation for the test strategy: how wizard decision
      logic would be tested independent of tkinter, and whether/how the
      GUI layer itself gets CI coverage (e.g. `xvfb-run`) versus staying
      manually verified -- with a reason, not a flat yes/no.
- [ ] The no-display / missing-`python3-tk` question is addressed in the
      recommendation (even if the answer is "out of scope, needs its own
      ticket").
- [ ] Any recommended implementation approach is filed as its own
      follow-up ticket rather than carried out inline here.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
