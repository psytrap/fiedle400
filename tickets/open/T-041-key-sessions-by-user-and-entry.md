# T-041: Key stored recordings by user and entry, not entry alone

- **Status:** Open
- **Priority:** Low (no device has shown a second user yet)
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`list_sessions`: `session_map[s.session_id] = s`;
    `download_all_sessions`: matching by `session_id`)
  - `fiedle400/cli.py` (session numbers shown and accepted by `sessions`, `download -s`, the
    wizard's selection)
  - `tests/test_hwsim_realtrace.py` (the `hwsim` fake's `fault` hook can describe more headers)

---

## Description & Context

Found in [T-039](../done/2026-W43/T-039-clarify-user-vs-session-concept.md). The `0xEC` header
names a recording by two numbers:
- byte 2 is the user;
- byte 3 is the entry, numbered within that user.

`SpO2.exe` keeps a table indexed by both, and the download request carries both
(PROTOCOL.md §3.2, §3.5). `fiedle400` keys its list by the entry number alone. In a pdb run
with two headers (user 1 / entry 1, then user 2 / entry 1), the second header replaced the
first in `session_map`, so one recording was listed and the other could not be downloaded.

The vendor captures show up to four entries, always for user 1 (PROTOCOL.md §3.13), so
keying by entry alone works on the devices seen so far. This is a latent issue for a second
user, not an observed one.

---

## Criteria

- [ ] `list_sessions` keeps every header, keyed by `(user_id, session_id)`, in the order the
      device sent them.
- [ ] What users see stays simple: one running number per recording in `sessions`, the
      wizard and `download -s`, mapped to `(user, entry)` internally. Show the user only when
      a device reports more than one.
- [ ] A test with the `hwsim` fake describing two users (and one with two entries for one
      user) lists and downloads both, sending the right bytes 3 and 4 in each `9D 04` request.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
