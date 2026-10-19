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

**Resolved, 2026-10-19: inject the data at open-time, don't fetch it.**
Browsers (Chrome especially) block a `file://` page from reading
*other* local files via `fetch`/XHR for security reasons, so passing
the `.spo2` path in a URL and having the page load it itself would not
work reliably. psytrap asked whether the data could instead be
**injected during the open process** -- yes, and it's the better
mechanism, not just a workaround:

- One **template** is the bundled static asset -- the chart/CSS/JS,
  maintained once, containing a placeholder
  (`<script id="spo2-data" type="application/json">{{DATA}}</script>`).
- At open time, `fiedle400` reads the template, substitutes the
  specific recording's decoded records in as inline JSON, writes the
  result to a temp file (`tempfile.NamedTemporaryFile(suffix=".html")`),
  and opens *that* via `_open_in_viewer`.
- The browser never fetches anything -- the data is already embedded
  in the page before it's opened, so the `file://` restriction never
  applies. Works unconditionally, in every browser. No file-picker
  fallback needed at all; drop that from scope.

So "static" = the template (one file, one place to maintain the chart
code); "dynamic" = the per-open injection step, which is what makes
each opened page show the right recording. `fiedle400`'s own Python
side does the data decoding (reusing the existing `.spo2`/engine
decode path, not a client-side binary-format reimplementation in JS)
and hands the template already-decoded JSON -- simpler than parsing
the binary format twice (once in Python, once in JS) for no benefit.

The `plot`/matplotlib relationship is still open (see T-006 -- `plot`
removal is explicitly blocked on this reaching parity, so this viewer
does need to actually chart SpO2 + heart-rate, not just dump raw
bytes).

## Still open for whoever executes this

- Where the template itself lives in the packaged binary (a PyInstaller
  resource vs. embedded as a Python string constant -- the latter
  avoids any resource-path resolution complexity across platforms).
- Exact temp-file lifecycle: left on disk for the user to reopen later,
  or cleaned up -- leaning toward leaving it (matches "recordings are
  never touched/removed automatically" elsewhere in this project), but
  not decided.

---

## Criteria

- [ ] One static HTML template (bundled, maintained once) exists; a
      per-open step injects the specific recording's decoded data into
      a copy of it, with no client-side `fetch`/XHR of another file.
- [ ] Wizard's download flow, when the chosen format is `spo2`, asks
      "Open it now? [y/N]" -- **default no**, opposite of the existing
      PNG-open prompt's default yes.
- [ ] Reuses `_open_in_viewer` (or equivalent) rather than a new
      OS-dispatch mechanism.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
