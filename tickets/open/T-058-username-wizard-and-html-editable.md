# T-058: Set a username via the wizard; show and edit it in the HTML viewer

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (`run_interactive_wizard`)
  - `fiedle400/spo2_viewer.py` (the generated HTML/JS)
  - `PROTOCOL.md` §3.2, `SPO2_FORMAT.md` (the `0xEC`/username field)

---

## Description & Context

psytrap request (German): "Nutzernahmen setzen via Wizard und Nutzernahmen
im HTML anzeigen und Editierbar machen" -- set a username through the
interactive wizard, and show/edit it in the HTML viewer.

**Important existing context, already decoded (T-039, `PROTOCOL.md:166`):**
the `0xEC` SESSION_INDEX header *does* have a real 6-byte ASCII username
field (`0x0E..0x13`), separate from the numeric 1-based `user` byte
(`fiedle400`'s `user_id`, byte 2). But every real capture seen so far shows
it hardcoded to `"user"` + `00 00` -- no evidence any PO-400 firmware or
`SpO2.exe` flow ever writes a real name there, and there's no decoded
command to *set* it on the device (not in the `0x9D`/`0xEC`/`0x90` command
tables). So this is very likely a **local-only** feature, not a
device-write feature -- needs confirming before implementation starts, not
assumed.

**Open questions to settle before implementing:**
- Can `fiedle400` actually write a username to the device at all? If not
  (likely, per the above), the wizard's "set a username" has to mean
  typing a local label associated with the numeric `user_id`
  (`~/.config/fiedle400` or similar), not a device write.
- Where does a locally-set name attach: to the `user_id` number (so it's
  remembered across sessions/downloads for "User #1"), or typed fresh per
  download/export?
- How does it reach the HTML viewer -- baked in at export time (read-only
  display unless regenerated), or live-editable in the browser with the
  same persistence question as [T-056](T-056-html-viewer-comment-field.md)'s
  comment field (no backing store for a static HTML file to save back to)?
  These two tickets likely want the same persistence mechanism -- worth
  deciding together, not independently.
- Does the always-`"user"` device field ever get *read* and shown as a
  fallback/default, distinct from the locally-editable name?

---

## Criteria

- [ ] Confirmed (not assumed) whether the device protocol supports writing
      a username at all; documented in `PROTOCOL.md` if this surfaces
      anything new
- [ ] Wizard has a step to set/edit a local username, persisted per
      `user_id`
- [ ] HTML viewer displays the username and allows editing it in the
      browser, with the persistence approach decided jointly with T-056
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
