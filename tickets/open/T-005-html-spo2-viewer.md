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

Open questions for whoever executes this (not decided here):
- What does the HTML viewer actually need to do -- parse the binary
  `.spo2` format client-side (JS reimplementing `SPO2_FORMAT.md`'s
  byte layout) and render a chart, or is it a thin wrapper that expects
  pre-converted JSON/CSV?
- Where does it live -- bundled as a static asset shipped with the
  binary (consistent with the zero-extra-dependency philosophy for the
  non-plot commands), opened via the same `_open_in_viewer` mechanism
  the PNG path already uses (a browser is also "the system's default
  viewer" for an `.html` file via `xdg-open`/`open`/`os.startfile`)?
- Does this duplicate or replace `fiedle400 plot` (which already needs
  matplotlib) -- or is the point specifically to view `.spo2` *without*
  that dependency?

---

## Criteria

- [ ] An HTML file exists that can read and display a `.spo2`
      recording (exact rendering fidelity vs. `fiedle400 plot`'s PNG
      not yet specified -- decide on execution).
- [ ] Wizard's download flow, when the chosen format is `spo2`, asks
      "Open it now? [y/N]" -- **default no**, opposite of the existing
      PNG-open prompt's default yes.
- [ ] Reuses `_open_in_viewer` (or equivalent) rather than a new
      OS-dispatch mechanism.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
