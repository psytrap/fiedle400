# T-093: Set a username via the wizard

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/cli.py` (`run_interactive_wizard`)
  - `PROTOCOL.md` §3.2, `SPO2_FORMAT.md` (the `0xEC`/username field)
  - A local persistence store (`~/.config/fiedle400` or similar -- not yet
    decided)
  - [T-058](T-058-html-viewer-username-display-and-edit.md) (the HTML
    viewer's display/edit half of the original combined request --
    split out from this ticket 2026-10-27)

---

## Description & Context

**Split 2026-10-27** from the original combined ticket (psytrap request,
German: "Nutzernahmen setzen via Wizard und Nutzernahmen im HTML anzeigen
und Editierbar machen" -- set a username via the wizard, and show/edit it
in the HTML viewer). The wizard/local-persistence half and the HTML
viewer's display/edit half are separable concerns -- this ticket is just
the wizard side; the viewer side is now [T-058](T-058-html-viewer-username-display-and-edit.md).

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
- Does the always-`"user"` device field ever get *read* and shown as a
  fallback/default, distinct from the locally-editable name?

## Criteria

- [ ] Confirmed (not assumed) whether the device protocol supports writing
      a username at all; documented in `PROTOCOL.md` if this surfaces
      anything new
- [ ] Wizard has a step to set/edit a local username, persisted per
      `user_id`
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

<!-- Filled in on completion -->
