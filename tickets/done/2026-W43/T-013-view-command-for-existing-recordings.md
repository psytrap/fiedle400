# T-013: `fiedle400 view FILE` opens the HTML viewer for an existing recording

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (new `view` subcommand next to `plot`; reuse
    `_open_spo2_viewer`)
  - `fiedle400/plot.py` (the file readers move out of it)
  - a new matplotlib-free module for the readers (name is the implementer's
    choice; `fiedle400/recording.py` suggested)
  - `fiedle400/spo2_viewer.py` (unchanged unless the records need adapting)
  - `README.md`, `tests/` (a CLI test with a mocked opener, a reader test
    that imports without matplotlib)

---

## Description & Context

From T-009 (and related to [T-012](T-012-make-html-the-default-download-output.md)). `plot` takes an existing `.spo2`, `.csv` or `.json` file, but the
HTML viewer is only reachable right after a wizard download. T-006 (remove
`plot`) cannot happen until the viewer can open a file that is already on disk.

`plot.py` imports matplotlib at the top, and it also holds the readers
(`read_spo2_file`, `read_csv_file`, `read_json_file`, `load_session_file`,
`find_latest_session_file`). Moving them into a module without that import is
the first step; `plot.py` then imports from it, so the tests that pin the
readers keep working.

Hard constraints: `view` must not need matplotlib; the zero-dependency promise
(RELEASE_PLAN G4) covers it. Under CI nothing may need a display or a browser:
launching goes through the mockable `_open_in_viewer`, same as the wizard.
When no browser can be opened, print the path of a saved HTML file instead of
failing (the existing fallback shape). Decide whether `view` writes the HTML
next to the recording or into a temp file, and say which in the notes.

---

## Criteria

- [x] The readers live in a module that imports without matplotlib
      (`plot` was removed in T-006 instead of kept).
- [x] `fiedle400 view FILE` opens the viewer for `.spo2`, `.csv` and `.json`
      files; without FILE it uses the latest recording like `plot` does.
- [x] No browser or display needed in tests (opener mocked); a clean venv
      without matplotlib runs `view --help` (G4).
- [x] `fiedle400 view FILE --convert [-o OUT]` writes `<recording>.html` (or OUT)
      without opening a browser; plain `view` leaves no file behind (psytrap, 2026-10-20).
- [x] README documents `view`.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy). New stdlib-only `fiedle400/recording.py` holds
`read_spo2_file`, `read_csv_file`, `read_json_file`, `load_session_file`,
`find_latest_session_file`, returning records shaped like the download output. `plot.py` is gone
(T-006), so nothing imports the readers from there any more.

Decisions (psytrap, 2026-10-20, replacing the first draft that wrote `<name>.html` and had
`--no-open`):
- `fiedle400 view [FILE]` opens the viewer without leaving a file: it reuses `_open_spo2_viewer`
  (temp page in the recording's folder, removed after the browser had 2 s; if no browser opens it
  prints where the data is). FILE defaults to the latest `.spo2/.csv/.json` in the current
  directory, then in the configured working directory.
- `--convert [-o OUT]` writes `<recording stem>.html` (or OUT) next to the recording, opens
  nothing, prints the path, exit 0. `-o` without `--convert` is a one-line error, exit 1 (chosen
  over "-o implies --convert" so that a typo cannot silently leave a file behind).
- Unreadable or missing file, bad extension, no first timestamp, no recording found: one line, exit 1.
  Values outside SpO2 1-100 / pulse 1-250 become None (probe-out when both).

Tests: `tests/test_recording.py` (19): .spo2 round trip via `build_spo2_binary` including a
probe-out second, csv and json round trips via `export_records`, missing first timestamp, bad
extension, missing and truncated file, `find_latest_session_file` picks the newest and ignores
other extensions, module imports with `sys.modules['matplotlib'] = None`; CLI tests with
`_open_in_viewer` mocked and `time.sleep` patched (temp page opened, contains the data, removed;
opener False names the recording; `--convert` writes next to the recording / to `-o` and does not
open; `-o` alone fails; no file found; unreadable file). `tests/test_cli_graceful.py` checks that
`import fiedle400` and `view --help` work with matplotlib blocked. Whole suite: 358 run, 0
failures, 7 skipped (live device). README documents `view`.

Left out: no PNG output (T-016 was Won't Do); `view` does not accept several files.
