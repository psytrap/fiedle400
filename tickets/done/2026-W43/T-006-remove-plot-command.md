# T-006: Remove `fiedle400 plot` once the HTML viewer supersedes it

- **Status:** Done
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

- [x] The HTML viewer (T-005, T-008) is shipped, `fiedle400 view FILE` exists
      (T-013) and covers what `plot` provides today (confirm feature parity
      explicitly before removing anything -- don't assume).
- [x] `plot` subcommand, `fiedle400/plot.py`, matplotlib bundling in
      `fiedle400.spec`, and the `fiedle400[plot]` extra are removed.
- [x] Every doc that mentions `plot` or the matplotlib dependency is
      updated (README, RELEASE_PLAN, DESIGN, PACKAGING) -- grep for
      "matplotlib" and "plot" across `*.md` before calling this done,
      not just the obvious files.
- [ ] A release-size comparison is recorded (the binary should shrink
      back down from the measured B1b numbers). *(Open: expected saving recorded in
      Execution Notes, the actual build is psytrap's local step.)*
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy). Removed: `fiedle400/plot.py`, `tests/test_plot.py`, the
plot and png wizard tests (`TestPlotWithoutMatplotlib`, `HAS_MATPLOTLIB` tests), the lazy
`plot_session` `__getattr__` and `__all__` entry, the `plot` extra in `pyproject.toml`,
`matplotlib` from `pip install` in `build-release.yml`, the second "with optional plot extra"
step in `tests.yml` (the first step already ran the stdlib-only suite), the wording in
`packaging/linux/install.sh`. `fiedle400.spec` now has `excludes=['matplotlib']` (nothing imports
it; keeps it out even if the build machine has it). `command_plot` and the `plot` subcommand were
replaced by `view` (T-013). The wizard's png option is gone (T-012).

Docs updated after grepping `matplotlib|plot` over `*.md`: README, PACKAGING, DESIGN (module table:
`plot.py` -> `recording.py`, `spo2_viewer.py` added; diagram), RELEASE_PLAN (quick commands, G1, G4,
G7, B1b with a "superseded by T-006" note; B1/B1b history rows kept), AGENTS.md ("missing optional
pieces"), SPO2_FORMAT.md (reader now `recording.py`), T-021 references, CHANGELOG 0.4.26 entry.
Left alone on purpose: history in CHANGELOG, `tickets/done/`, `handoff/`, DONE.md timeline,
RELEASE_PLAN history lines (G7 "plotted" re-verification rows, now marked as done with the old
PNG), the "scratch plots" line in AGENTS.md workspace rules (about agent scratch files, not the
product), and the release-note comment in `build-release.yml` (history).

Feature parity, stated plainly. `plot` drew: SpO2 and heart-rate lines, reference lines at 95/90 %
SpO2 and 60/100 bpm, min/avg/max stats, time below 90 %, dropouts, written as a PNG. The viewer
has: both curves, all of those statistics, "time below criteria level" with an adjustable level
(default 88 %, not a fixed 90 %), dropouts, plus the desaturation report; and a print button
instead of a PNG file (T-016 PNG export was Won't Do). **The viewer has no 95/90 % or 60/100 bpm
reference lines.** That is a real, accepted difference.

Release size: expected saving is the B1b measurement (8.8 MB without, 44.0 MB with matplotlib,
+35.2 MB, ~5x). I did not measure it: `pip install matplotlib` was not possible in this sandbox
(no network), and there was no clean "before" tree to build. The actual before/after build is
psytrap's local step, so the size criterion stays unticked.

Tests: 358 run, 0 failures, 7 skipped (live device); pyflakes: only the two known warnings
(`readline` in cli.py, unused `sys` in tests/test_sync_patch.py, which was already there).
