# T-039: Clarify "User" vs "Session" in the device protocol

- **Status:** Open
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

- [ ] A written definition of "User slot" vs "segment" vs "`fiedle400`
      session," cross-referenced against `PROTOCOL.md` §3.2 and §3.13 and
      the vendor disassembly, with each place the terms are used reconciled
      or explicitly left open.
- [ ] `PROTOCOL.md` updated (or a correction flagged) wherever this
      ticket's findings change what's stated today.
- [ ] If the ambiguity can't be resolved from existing docs/recordings, the
      ticket says so plainly rather than guessing, per `AGENTS.md` ("never
      state a protocol fact you have not seen in a recording").
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
