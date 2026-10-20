# T-012: Make the HTML viewer the default download output

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (wizard format menu ~line 975, the
    `[y/N]` "Open it in the HTML viewer now?" prompt ~line 1059,
    `parser_dl`'s `-f/--format` choices ~line 1119,
    `_export_records_to_file`/`_open_spo2_viewer` ~lines 371, 228)
  - `tests/test_cli_graceful.py` (`TestOpenInViewer`, format-selection
    tests)
  - `README.md`, `RELEASE_PLAN.md` (wherever default format/behaviour
    is documented)

---

## Description & Context

psytrap: make the HTML viewer the default output of a download,
rather than today's behaviour -- save as `.spo2` by default, then
separately ask "Open it in the HTML viewer now? [y/N]"
(`fiedle400/cli.py:1059`), defaulting to *not* opening it.

**This is a direct instruction to change the default, not a repeat of
[T-009](T-009-html-viewer-as-default-output.md).** T-009 is still open
as the evaluation of *whether* to do this; this ticket is the
follow-up it already anticipated ("any recommended change is filed as
its own follow-up ticket rather than implemented inline"). T-009's own
open questions become this ticket's concrete work, not things to
re-debate:

- **Interactive wizard:** flip the "open in viewer" prompt's default
  from `[y/N]` to `[Y/n]` (or open it unconditionally and drop the
  prompt entirely -- decide which when executing), without removing
  the ability to decline and keep just the raw file.
- **Non-interactive `download -f/--format`:** the flag's choices today
  are `spo2`/`csv`/`json` only (`cli.py:1119`), with `spo2` as the
  default. Give it an explicit `html` choice rather than silently
  changing what the existing default (`spo2`) produces -- a script
  that already passes no `-f` and expects a `.spo2` file must keep
  getting one unless this ticket's execution explicitly decides to
  change that default too and calls it out in `Execution Notes` and
  the CHANGELOG as a breaking CLI change.
- **Raw data file:** keep writing the underlying `.spo2`/`csv`/`json`
  data alongside the HTML viewer -- the viewer is a presentation of
  the data, not a replacement for having it. Never make the HTML file
  the *only* output.
- **Headless/CI safety:** the viewer-open step must still degrade
  gracefully when no display/browser is available (`_open_in_viewer`'s
  existing behaviour, mirrored in `TestOpenInViewer`) -- becoming the
  default must not turn a currently-silent no-op into a hard failure
  for a scripted or headless `download` run.
- Interaction with **T-006** (remove `plot`): once HTML is the
  default, that strengthens the case to retire the wizard's separate
  `png`/matplotlib option -- but T-006 stays explicitly blocked on its
  own criteria (feature parity, confirmed, not assumed); don't fold it
  into this ticket.

---

## Criteria

- [ ] Interactive wizard opens the HTML viewer by default after a
      successful download (prompt default flipped, or prompt removed
      -- document which was chosen and why in Execution Notes), while
      still writing the raw data file every time.
- [ ] Non-interactive `download -f/--format` behaviour is decided
      explicitly: either it gains an `html` choice without changing
      the current default, or the default itself changes -- and if
      it changes, that's called out as a breaking CLI change in
      `CHANGELOG.md`, not a silent behaviour shift.
- [ ] The HTML file is never the only output written; the raw
      `.spo2`/`csv`/`json` data is always still saved.
- [ ] A headless/no-browser environment (mirroring CI) still
      completes a download without error when the viewer can't
      actually open -- verified via the existing `TestOpenInViewer`-
      style mocking, not assumed.
- [ ] `README.md`/`RELEASE_PLAN.md` updated to describe the new
      default.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
