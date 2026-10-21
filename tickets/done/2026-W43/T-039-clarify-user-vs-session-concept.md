# T-039: Clarify "User" vs "Session" in the device protocol

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `PROTOCOL.md` §3.2 (`0xEC` Session Header), §3.13 (`FLASH_CLEAR`)
  - `fiedle400/engine/device.py` (where `0xEC` byte `0x02`/`0x03` are read)

---

## Description & Context

psytrap: the "User" and "Session" concepts in the protocol docs don't add up
-- this ticket is to work out what the device actually means by each, not to
fix anything yet.

Two places in `PROTOCOL.md` use these words for what may or may not be the
same thing:

- §3.2, the `0xEC` session header: byte `0x02` is `fiedle400`'s "user id" but
  the vendor disassembly calls it "total segments count"; byte `0x03` is
  `fiedle400`'s "session id" but the disassembly calls it "1-based segment
  number." Every real recording captured so far has `01 01` in both bytes,
  so the two readings are indistinguishable with the data on hand -- neither
  is confirmed (`PROTOCOL.md:156-157`).
- §3.13, `FLASH_CLEAR`: `0x91`..`0x96` are documented as erasing "recorded
  session data for User 1..6" -- i.e. a *user slot* (1 of up to 6), not an
  individual recording/session within a slot.

So "session" is used for at least two different things in the docs: a
numbered slot under a user (§3.2's "segment"), and, elsewhere in this
project's own terminology (e.g. `fiedle400 sessions`, `.spo2` exports), a
single recorded download. It is not established whether the device's
"segment" and the CLI's "session" (one `.spo2` recording) are the same
concept, or whether "User 1..6" is a login-style account slot distinct from
both.

What is NOT known:
- Whether a "User" (1..6) can hold more than one "segment"/session
  simultaneously, or whether the device has only ever been seen with one.
- Whether `fiedle400 sessions`' notion of a session id matches the device's
  "segment index," or is purely a `fiedle400`-side construct.
- Whether any real device/recording exists with segment count/index other
  than `01 01` that would let this be tested empirically.

---

## Criteria

- [x] A written definition of "User slot" vs "segment" vs "`fiedle400`
      session," cross-referenced against `PROTOCOL.md` §3.2 and §3.13 and
      the vendor disassembly, with each place the terms are used reconciled
      or explicitly left open.
- [x] `PROTOCOL.md` updated (or a correction flagged) wherever this
      ticket's findings change what's stated today.
- [x] If the ambiguity can't be resolved from existing docs/recordings, the
      ticket says so plainly rather than guessing, per `AGENTS.md` ("never
      state a protocol fact you have not seen in a recording").
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud, patch 0030). No code changed; `PROTOCOL.md` §3.2, §3.5 and
§3.13 updated.

**Definitions.** All of these come from `SpO2.exe`. Correction (2026-10-21): the archived vendor
captures do show entries 1..4 for user 1, each later header with bit 6 clear except the last
(`PROTOCOL.md` §3.13); a second user has never been seen.
- **User:** `0xEC` byte 2, 1-based. The program keeps one username and one list of entries
  per user, and sends the number back as byte 3 of the `0x9D` page request. This is
  `fiedle400`'s `user_id`.
- **Entry:** `0xEC` byte 3, 1-based, **numbered within its user**. It is byte 4 of the page
  request. This is `fiedle400`'s `session_id`.
- **`fiedle400` session:** one entry. It is one `0xEC` header and one recording, and it is
  identified by *both* numbers. The device has no separate "segment" concept: "Total
  Segments" / "Segment Index" came from a wrong disassembly citation (below).
- **`0x91`..`0x96` (§3.13):** not per-user erase commands. A later static pass (T-037) showed
  they are a separate download family answered by `0xE1`..`0xE6`; the real erase is `9D 7F`,
  which names a recording by user and entry like the download request.

**Where that comes from (static analysis of `SpO2.exe`):**
- The `0xEC` reply handler is the case at `0x4ea405` of the reply parser. It stores:
  - byte 1's low nibble at `+0x2f8`;
  - bit 6 at `+0x2fc`;
  - byte 2 at `+0x2f0`;
  - byte 3 at `+0x2f4`;
  - the start time, the 28-bit sample count (`+0x2ac`) and the 6-byte username (`+0x2b0`).
- The recordings dialog (`0x4b8807`-`0x4b8d9d`):
  - resizes its per-user tables (`+0xae0`, `+0xad0`, `+0xaf0`, `+0x1560`) to `byte2` entries
    and user `byte2`'s entry list to `byte3`;
  - writes the start time and sample count to `[byte2 - 1][byte3 - 1]` and the username to
    `[byte2 - 1]`;
  - then, **while bit 6 is clear**, sends `9C 01` again (`0x4b8d55`). So bit 6 means "last
    header", not "data ready" as §3.2 said. `fiedle400` already stops on it.
- All three `0x9C` call sites send `9C 01`; the byte is never a user selector.
- The download loop sends `9D 04 type user entry ...` with `user` and `entry` taken from
  those table indices plus one (`0x4b8fd2`-`0x4b9059`). The `0x9D` builder (`0x4bc54b`)
  writes its arguments to bytes 1-7, which is the same layout `fiedle400` uses.
- Byte 1's low nibble is compared with 1. The result sets a flag (`dlg+0x11c`) that many
  download paths read. What it means is **not decoded**; it is `0` in every recording.

**Wrong citation.** `analysis/bum400_20260906_100516.md` §A.2 (and, via it,
`analysis/po400_bytemap_reference.md`) puts the handler at `0x004c587a` with fields
`[this+0x1e8]`/`[this+0x1ec]`. That does not match the binary: `0x4c587a` is unrelated code, and
`+0x1e8`/`+0x1ec` are not used by this class. `PROTOCOL.md` now carries the correction. The
two analysis files were left as they are (CRLF with an embedded NUL), and the correction
points at them.

**Debugger run** (`python3 -m pdb`, breakpoints at `parsers.py:97`, in
`parse_session_index_table`, and `engine/device.py:505`, in `list_sessions`, against the
`hwsim` fake):
- On the recorded trace (`tests/fixtures/cli-exchange.trace.json`):
  - The header is `ec 40 01 01 1a 09 1e ...`: bit 6 set, `user_id = 1`, `sess_id = 1`.
  - `session_map` ends as `{1: (1, 1)}`, which is one recording.
- With the `0xEC` replies rewritten through the fake's `fault` hook to describe two entries
  (user 1 / entry 1 with bit 6 clear, then user 2 / entry 1 with bit 6 set):
  - `list_sessions` asks twice and parses both, as the vendor does.
  - `session_map` goes from `{1: (1, 1)}` to `{1: (2, 1)}`: the second header **overwrites the
    first**, because the map is keyed by entry number alone.
  - The result is one recording where `SpO2.exe` would list two.

  This is hypothetical (no device has shown a second user), so nothing was fixed here. It is
  [T-041](../../open/T-041-key-sessions-by-user-and-entry.md).

**What would settle the open points:** a capture of a PO-400 switched to a second user, if its
menu allows that, through `tests/capture_tools`. Reading only, never erasing. Several entries
for one user are already in the archived captures.
