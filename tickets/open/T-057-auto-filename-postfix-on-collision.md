# T-057: Automatic filename choice -- insert the postfix right away

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/export.py` (`export_records`, the auto-filename path)
  - `fiedle400/cli.py` (`generate_iso_filename`, `get_next_available_filename`
    -- the interactive wizard already does this right)

---

## Description & Context

psytrap request (German): "Automatische dateinamen wahl. Gleich das postfix
einfügen." -- when a filename is chosen automatically (not typed by the
user), insert the disambiguating postfix (`_1`, `_2`, ...) up front if the
plain name would collide, instead of silently overwriting.

Today this is inconsistent between the two code paths that generate a
default filename:

- **Interactive wizard** (`fiedle400/cli.py` around line 1023): generates
  `default_fn` via `generate_iso_filename`, and if the chosen output path
  already exists, prompts and offers `get_next_available_filename`'s `_1`/
  `_2` counter suffix. Already does the right thing, just reactively
  (after a prompt), not immediately.
- **Non-interactive `fiedle400 download` / `_export_records_to_file`**
  (`fiedle400/export.py:222-226`): builds `fiedle400_all_sessions_<second
  -precision timestamp>.<ext>` and writes to it directly --
  **no existence check at all**. Two downloads inside the same wall-clock
  second (fast scripted re-runs, or a system clock that only has whole-second
  resolution) silently overwrite the earlier file with no warning. This is
  the gap psytrap is pointing at.

---

## Criteria

- [ ] `export_records`'s auto-generated-name path checks for an existing
      file at the candidate path and, if found, appends a `_N` postfix
      (reusing `get_next_available_filename` or equivalent) before writing
      -- no silent overwrite when no explicit `-o`/filename was given
- [ ] Behavior matches across the wizard and the non-interactive path (one
      shared helper, not two independent implementations of "pick the next
      free name")
- [ ] A test exercises the same-second-collision case (two downloads with
      the clock mocked to the same timestamp) and confirms the second file
      lands at `..._1.<ext>`, not overwriting the first
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
