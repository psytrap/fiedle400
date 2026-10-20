# T-006: Remove `fiedle400 plot` once the HTML viewer supersedes it

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (`command_plot`, the `plot` subparser)
  - `fiedle400/plot.py`
  - `fiedle400.spec` (matplotlib bundling, RELEASE_PLAN.md B1b)
  - `pyproject.toml` (`fiedle400[plot]` extra)
  - `README.md`, `RELEASE_PLAN.md`, `DESIGN.md`, `PACKAGING.md`
  - `tests/test_cli_graceful.py` (`TestPlotWithoutMatplotlib`), any other
    `plot`-specific tests

---

## Description & Context

psytrap, while discussing T-005 (the HTML `.spo2` viewer): once that
viewer exists and covers what `fiedle400 plot` is for, `plot` itself
becomes redundant and should be removed -- **later on**, not now. This
ticket exists to track that intent so it isn't lost, not to do it yet.

`plot` currently exists specifically because viewing a recording
needed matplotlib, which cost +35.2 MB (~5x) in the bundled binary
(RELEASE_PLAN.md B1b, decision to bundle it anyway after measuring the
real cost). If an HTML viewer does the same job with no extra runtime
dependency, that cost -- and the whole `plot`/matplotlib code path --
has no remaining reason to exist.

**Blocked on T-013** (updated 2026-10-20). T-005 is done and, with T-008
(v0.4.18), the viewer matches the chart `plot` draws and goes beyond it. What
is missing is a way to open an existing recording file in the viewer: `plot`
takes any `.spo2`/`.csv`/`.json`, the viewer is only offered after a wizard
download. T-013 adds `fiedle400 view FILE` and moves the file readers out of
`plot.py`; do not execute this ticket before that is true.

---

## Criteria

- [ ] The HTML viewer (T-005, T-008) is shipped, `fiedle400 view FILE` exists
      (T-013) and covers what `plot` provides today (confirm feature parity
      explicitly before removing anything -- don't assume).
- [ ] `plot` subcommand, `fiedle400/plot.py`, matplotlib bundling in
      `fiedle400.spec`, and the `fiedle400[plot]` extra are removed.
- [ ] Every doc that mentions `plot` or the matplotlib dependency is
      updated (README, RELEASE_PLAN, DESIGN, PACKAGING) -- grep for
      "matplotlib" and "plot" across `*.md` before calling this done,
      not just the obvious files.
- [ ] A release-size comparison is recorded (the binary should shrink
      back down from the measured B1b numbers).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
