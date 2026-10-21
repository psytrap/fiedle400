# T-037: `fiedle400 clear`'s per-session erase sequence is unverified against a real capture

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (the `clear` command's byte sequences)
  - `PROTOCOL.md` §3.13 (`FLASH_CLEAR`)

---

## Description & Context

`PROTOCOL.md` §3.13 documents the vendor's erase opcodes (`0xAA` full erase,
`0x91`..`0x96` per-user erase) from the `SpO2.exe` disassembly, but notes none
of them has ever been captured in a real recording.

`fiedle400 clear` in `engine/device.py` does not send those documented bytes.
It sends a different, undocumented sequence: `0xAF`, then either `0xAB 01
[id]` for a single session or `0xAA 80 80` / `0xAB 80 80` / `0xAC 80 80` for
all sessions, each with the `7D 81` prefix. `PROTOCOL.md` already flags this
as "none of this is documented or recorded; treat `clear` as unverified."

What is NOT known:
- Whether `0xAB 01 [id]` actually erases only the named session, erases more
  than that, or does something unrelated -- there is no capture of it
  succeeding, partially succeeding, or failing.
- Whether the `0xAA 80 80` / `0xAB 80 80` / `0xAC 80 80` "all sessions" forms
  behave as their naming implies.

This matters because `fiedle400 clear` is a destructive, user-facing command
run against real device flash holding real recorded sessions -- unlike
`download`/`sessions`/`info`/`selftest`, which are read-only per `AGENTS.md`.

## Safety

- Never erase device flash as part of investigating this ticket without the
  owner's explicit, informed go-ahead for that specific run, and only against
  sessions that are not needed (or are backed up first via `download`).
- No automated test may send any of these sequences to a real device.

---

## Criteria

- [ ] A written recommendation on how to verify `clear`'s actual behavior
      safely (e.g. a disposable test recording, captured with
      `record_exchange.py`, erased deliberately with explicit consent) --
      or a decision to leave it unverified for now, with a reason.
- [ ] If verified: `PROTOCOL.md` §3.13 updated with the real behavior and a
      capture reference; if not verified: the "unverified" note stays as-is.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
