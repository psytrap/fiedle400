# T-056: Comment field in the HTML viewer

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the generated HTML/JS)

---

## Description & Context

psytrap request (German): "Kommentar feld im HTML" -- a free-text comment/
notes field in the HTML viewer, so a recording can carry a short note (how
the night felt, what was unusual, device placement, etc.) alongside the
chart and report.

Open questions this ticket needs to settle, not yet decided:
- **Persistence:** the viewer is a single static, self-contained HTML file
  per `fiedle400 view`/`download` (T-005/T-012) -- there is no backing store
  to save a typed comment back to. Options: (a) display-only, read from a
  field already present in the source `.spo2`/`.csv`/`.json` if one exists;
  (b) editable in the browser but only persisted via the browser's own
  "Save As" / print, not written back to the original file; (c) something
  that round-trips into the `.spo2`/`.json` export so a comment survives
  re-opening -- needs its own decode/encode work if the native `.SpO2`
  format has no free-text field at all (check `SPO2_FORMAT.md`, not yet
  checked for this ticket).
- Where it sits in the page (top, near the report table, printable or not).

Related: [T-058](T-058-username-wizard-and-html-editable.md) wants an
editable username in the same viewer, with the same "no backing store for
a static HTML file" persistence question -- worth designing together.

---

## Criteria

- [ ] Persistence approach decided and written down above (or in Execution
      Notes) before implementing
- [ ] Comment field added to the viewer per that decision
- [ ] If round-tripping into a file format, `SPO2_FORMAT.md` documents the
      field and both read and write paths handle it
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
