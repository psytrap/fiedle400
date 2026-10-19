# T-005: HTML viewer for `.spo2` files, offered from the wizard

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud (no hardware involved; pure software/UI work)
- **Scope & Relevant Files:**
  - A new HTML file/template able to read and render a `.spo2` file
    (location TBD -- a static page shipped with the tool, or generated
    per-export)
  - `fiedle400/cli.py` (`run_interactive_wizard`'s download flow)
  - `tests/test_cli_interactive.py`

---

## Description & Context

psytrap: "have a html in fiedle400 that can read spo2. Lets have a
step in the wizard that asks for opening spo2 when extracting spo2
that defaults to no."

No HTML viewer exists in the project today (checked: the only `.html`
in the repo is a build-tool xref artifact, unrelated).

The wizard already has a precedent for exactly this shape of prompt --
after rendering a PNG plot it asks `"Open the plot now? [Y/n]"`
(default **yes**, `fiedle400/cli.py` around line 896, `_open_in_viewer`
for the OS-native opener). This ticket is the same idea, but:
- for the raw `.spo2` **data** export (not the PNG plot path), via a
  **new HTML page** this project doesn't have yet, not the OS's native
  file opener;
- **defaulting to no**, the opposite of the PNG prompt's default --
  psytrap's request was explicit about this, presumably because
  opening a browser is heavier/more intrusive than opening an image
  viewer, or because the HTML viewer is new/unproven.

## Decided (psytrap, 2026-10-19, discussed before execution)

**Static, not generated-per-export.** One HTML file bundled with the
tool (consistent with the zero-extra-dependency philosophy for the
non-plot commands), not a fresh file written out per download. The
wizard opens this bundled page and points it at the specific `.spo2`
file just downloaded -- "po400 wizard opens bundled static html +
dynamic spo2."

**Known technical wrinkle, not yet resolved:** browsers (Chrome
especially) block a `file://` page from reading *other* local files
via `fetch`/XHR for security reasons, so passing the `.spo2` path in a
URL and having the page auto-load it may simply not work across
browsers. The robust fallback: a plain `<input type="file">` picker in
the static page itself -- the user grants access via the native file
dialog, which always works regardless of browser security policy. The
wizard can still make this painless by printing the exact file path
right before opening the page, so the user knows exactly what to pick.
Whoever executes this should try the auto-load-via-path convenience
first but must not depend on it -- the file-picker path needs to work
unconditionally.

Parse-client-side-vs-pre-converted-JSON and the `plot`/matplotlib
relationship are still open (see T-006 -- `plot` removal is explicitly
blocked on this reaching parity, so this viewer does need to actually
chart SpO2 + heart-rate, not just dump raw bytes).

## Still open for whoever executes this

- Parse the binary `.spo2` format client-side (JS reimplementing
  `SPO2_FORMAT.md`'s byte layout), or read a CSV/JSON export instead --
  client-side binary parsing avoids needing any pre-conversion step at
  all, which fits "static page, not generated per export" better.
- Where exactly does the bundled asset live in the packaged binary
  (PyInstaller resource vs. a file written next to the binary on
  install) -- opened via the same `_open_in_viewer` mechanism the PNG
  path already uses (a browser is also "the system's default viewer"
  for an `.html` file via `xdg-open`/`open`/`os.startfile`).

---

## Criteria

- [ ] One static, bundled HTML file (not generated per export) exists
      that can read and display a `.spo2` recording -- works via a
      file picker unconditionally, auto-load-via-path as a bonus if
      the browser allows it, not a requirement.
- [ ] Wizard's download flow, when the chosen format is `spo2`, asks
      "Open it now? [y/N]" -- **default no**, opposite of the existing
      PNG-open prompt's default yes.
- [ ] Reuses `_open_in_viewer` (or equivalent) rather than a new
      OS-dispatch mechanism.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
