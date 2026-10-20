# T-009: Evaluate making the HTML viewer the default output (CI testability preserved)

**Superseded by direct instruction, 2026-10-20:** psytrap decided this
directly rather than waiting on the evaluation below -- see
[T-012](T-012-make-html-the-default-download-output.md), which carries
out the change and absorbs this ticket's open questions (non-interactive
`-f/--format` behaviour, keeping the raw data file, headless/CI safety)
as its own criteria. Left open rather than closed: the CI-testability
constraint recorded below is still the standing reason a native GUI
toolkit was never considered as the mechanism, and is worth keeping as
a citable record independent of T-012's execution.

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (interactive wizard's format menu at line ~975,
    the `[y/N]` "Open it in the HTML viewer now?" prompt at line ~1059,
    `parser_dl`'s `-f/--format` choices at line ~1119)
  - `README.md`, `RELEASE_PLAN.md` (wherever the current default format
    is documented)
  - `tests/test_cli_graceful.py` (`TestOpenInViewer`, the existing
    headless-safe precedent for testing this code path)
  - `.github/workflows/tests.yml` (no display server / no browser
    available there -- any change must keep passing here unmodified,
    or the workflow's own constraints become part of the change)

---

## Description & Context

psytrap: evaluate whether the HTML `.spo2` viewer (T-005, extended by
T-008) should become the **default** way a downloaded recording is
presented, instead of today's opt-in behaviour -- the wizard saves in
`spo2` format by default and then asks "Open it in the HTML viewer
now? [y/N]" (`fiedle400/cli.py:1059`), i.e. the default answer is *no*.

This is an evaluation ticket, same shape as T-007: it exists to hold
the question and a written recommendation, not to flip the default
in the same turn.

Concrete angles to evaluate, not a committed list:
- Flip the wizard prompt's default to `[Y/n]` (viewer opens unless the
  user opts out), vs. leaving data-only as the safer default for a
  headless/SSH session where a browser can't open anyway.
- Whether `download`'s non-interactive `-f/--format` flag
  (`spo2`/`csv`/`json` today, `cli.py:1119`) should gain an `html`
  choice of its own, independent of the wizard's separate "open in
  viewer" step -- and if so, whether it replaces or supplements the
  wizard prompt.
- Whether the raw `.spo2` file should still always be written
  alongside the viewer (so a script relying on today's default output
  file keeps working), or only on request -- i.e. this must not
  silently change what non-interactive scripted use of `download`
  produces by default.
- Interaction with **T-006** (remove `plot` once the HTML viewer has
  parity): if HTML becomes the default *presentation*, that's a
  stronger reason to retire `plot`'s separate `png` menu option, not
  just matplotlib's bundling cost.
- Whether this should wait on T-008's still-open items (per-channel
  switch, print) landing first, since "default output" implies the
  viewer is good enough to be seen first, not as a fallback.

**Hard constraint, not optional (psytrap): must keep the GitHub
Actions CI testable headlessly.** `.github/workflows/tests.yml` runs
`python3 -m unittest discover` with no display server and no real
browser available. Today's design already respects this: the viewer
is plain HTML generated as a string (`spo2_viewer.build_viewer_html`,
asserted against directly in tests) and *launching* it is a thin,
mockable OS-opener call (`cli._open_in_viewer`, `TestOpenInViewer` in
`tests/test_cli_graceful.py` mocks `subprocess.Popen`/`shutil.which`
rather than opening a real browser). Any recommendation here --
whether or not the default changes -- must preserve that property:
nothing added may require a real display, a real browser process, or
an actually-rendered page to pass CI. If a native GUI toolkit
(tkinter/Qt/etc.) is ever raised as an alternative to the HTML
viewer, that is the specific reason to reject it outright rather than
re-litigate per feature: it would need `xvfb-run` or a UI-automation
layer CI doesn't have today, where HTML-in-a-string does not.

---

## Criteria

- [ ] A written recommendation exists (this ticket's own Execution
      Notes): keep the current opt-in default, or change it, with a
      reason -- not a flat "yes/no" with no justification.
- [ ] If changing the default is recommended, the non-interactive
      `download` CLI behaviour (scripted use, no prompts) is addressed
      explicitly: what it writes by default today must keep working
      unless this ticket's follow-up says otherwise.
- [ ] Any recommended change is filed as its own follow-up ticket
      rather than implemented inline here.
- [ ] The recommendation explicitly confirms it keeps the viewer
      testable headlessly under GitHub Actions (no real display or
      browser needed in CI) -- not silently assumed.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
