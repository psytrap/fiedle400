# T-012: Make the HTML viewer the default download output

- **Status:** Done
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
[T-009](../done/2026-W43/T-009-html-viewer-as-default-output.md).** T-009 is still open
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

- [x] *(Superseded by psytrap, 2026-10-20: the wizard saves the HTML by default and asks
      "Open it in your browser now? [y/N]", default no; no raw file is written.)*
      Interactive wizard opens the HTML viewer by default after a
      successful download (prompt default flipped, or prompt removed
      -- document which was chosen and why in Execution Notes), while
      still writing the raw data file every time.
- [x] Non-interactive `download -f/--format` behaviour is decided
      explicitly: either it gains an `html` choice without changing
      the current default, or the default itself changes -- and if
      it changes, that's called out as a breaking CLI change in
      `CHANGELOG.md`, not a silent behaviour shift.
- [x] *(Superseded by psytrap, 2026-10-20: by default the HTML file is the only output;
      `.spo2`/csv/json only on request.)* The HTML file is never the only output written; the raw
      `.spo2`/`csv`/`json` data is always still saved.
- [x] A headless/no-browser environment (mirroring CI) still
      completes a download without error when the viewer can't
      actually open -- verified via the existing `TestOpenInViewer`-
      style mocking, not assumed.
- [x] `README.md`/`RELEASE_PLAN.md` updated to describe the new
      default.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy). **psytrap's decision of 2026-10-20 overrides the ticket text:**
the default download output is the HTML viewer file that the user can open later; by default no
`.spo2` is written. This is a breaking CLI change (CHANGELOG 0.4.26, README, RELEASE_PLAN):
- `download -f` choices are now `html`(default)/`spo2`/`csv`/`json` (`export.EXPORT_FORMATS`);
  `-o x.html|.spo2|.csv|.json` picks the format by extension. `export_records(fmt="html")` writes
  `spo2_viewer.build_viewer_html(records)`; the library default of `export_records` itself stays `"spo2"`.
- Wizard format menu: `[1] html (default) [2] spo2 [3] csv [4] json`. After saving an html file it
  asks "Open it in your browser now? [y/N]" (default No, so the prompt was kept and the default is
  "no", rather than flipped to yes or removed). `y` opens the saved file; if no browser opens it
  prints the path. For spo2 the old temp-viewer prompt is unchanged. png is gone (T-006).
- Non-interactive `download` never opens a browser (tested: opener not called).

Criteria as ticked: the first (viewer opens by default) and the third ("HTML never the only
output") were deliberately overridden by psytrap and are ticked as **superseded**, not met as
written: the HTML is the only file by default and opening is opt-in. The `-f` decision is the second
criterion's second branch (default changed, breaking, in CHANGELOG). The headless criterion is met
trivially for `download` (never opens) and for the wizard by the mocked opener returning False.

Tests: wizard Enter at format saves via `_export_records_to_file(..., "html")` with a `.html` name and
asks the [y/N] prompt without opening; `y` opens the saved path; opener False prints the path;
`download` through `cli.main` with a mocked engine writes one `.html` containing the records and no
`.spo2`; `-f spo2` still writes `.spo2`; `export_records("html")`. Existing wizard tests that assumed
`.spo2` were updated (overwrite tests now key on `.html`; the spo2 viewer tests choose format "2").
Suite: 358 run, 0 failures, 7 skipped (live device).
