# T-058: Show and edit a username in the HTML viewer

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the generated HTML/JS)
  - `PROTOCOL.md` §3.2, `SPO2_FORMAT.md` (the `0xEC`/username field)
  - [T-056](T-056-html-viewer-comment-field.md) (shares the same
    "editable field in a static, self-contained HTML file" persistence
    question -- worth deciding together, not independently)
  - [T-093](T-093-set-username-via-wizard.md) (the wizard/local-persistence
    half of the original combined request -- split out of this ticket
    2026-10-27; this ticket is downstream of whatever T-093 decides a
    locally-set username actually is)

---

## Description & Context

**Split 2026-10-27** from the original combined ticket (psytrap request,
German: "Nutzernahmen setzen via Wizard und Nutzernahmen im HTML anzeigen
und Editierbar machen" -- set a username via the wizard, and show/edit it
in the HTML viewer). This ticket is just the HTML viewer's display/edit
half; setting a username via the wizard (and the local-persistence
question that comes with it) is now [T-093](T-093-set-username-via-wizard.md).

**Important existing context, already decoded (T-039, `PROTOCOL.md:166`):**
the `0xEC` SESSION_INDEX header *does* have a real 6-byte ASCII username
field (`0x0E..0x13`), separate from the numeric 1-based `user` byte
(`fiedle400`'s `user_id`, byte 2). But every real capture seen so far shows
it hardcoded to `"user"` + `00 00` -- no evidence any PO-400 firmware or
`SpO2.exe` flow ever writes a real name there. This ticket's "show" side
most likely means showing a *locally* set name (from T-093), with the
always-`"user"` device field as, at best, a fallback/default -- not a
reliable source of a real name.

**Open questions to settle before implementing:**
- How does a username reach the HTML viewer -- baked in at export time
  (read-only display unless regenerated), or live-editable in the browser
  with the same persistence question as T-056's comment field (no backing
  store for a static HTML file to save back to)? T-056 and this ticket
  likely want the same persistence mechanism.
- Does the always-`"user"` device field ever get *read* and shown as a
  fallback/default, distinct from the locally-editable name from T-093?

## Criteria

- [ ] HTML viewer displays the username and allows editing it in the
      browser, with the persistence approach decided jointly with T-056
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

<!-- Filled in on completion -->
