# T-013: `fiedle400 view FILE` opens the HTML viewer for an existing recording

- **Status:** Open
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

- [ ] The readers live in a module that imports without matplotlib; `plot`
      still works and its tests pass.
- [ ] `fiedle400 view FILE` opens the viewer for `.spo2`, `.csv` and `.json`
      files; without FILE it uses the latest recording like `plot` does.
- [ ] No browser or display needed in tests (opener mocked); a clean venv
      without matplotlib runs `view --help` (G4).
- [ ] README documents `view`.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
