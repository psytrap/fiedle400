# T-071: Manual-mode subframe bytes 3..4, `D0` bytes 8..9, and `D0` kinds 1/4

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `PROTOCOL.md` §3.14 (Manual Recording Protocol -- the "second capture"
    note, 2026-10-21)
  - `tickets/done/2026-W43/T-051-manual-mode-remaining-protocol-questions.md`
    (where these were last investigated, and closed without resolving them)

---

## Description & Context

T-051 (closed 2026-10-21) settled Manual-mode sample timing and the
"one sample per second" question using a real 315-record, 5-minute
recording, but left three byte-level mysteries explicitly undecoded,
documented in `PROTOCOL.md` §3.14 rather than tracked as a ticket:

- **Subframe bytes 3..4** (SpO2 and Pulse subframes): an earlier
  single-sample capture suggested these mark finger-on/off per subframe,
  but the second, larger capture disproves that -- the bytes vary
  subframe-to-subframe even while every sample in a subframe has the
  finger on. Likely a running counter or checksum rather than a status
  flag; no hypothesis currently fits all the observed values.
- **`D0` header bytes 8..9**: always `00 00` in every capture seen so
  far. Unknown meaning, never observed non-zero.
- **`D0` kind byte**: only ever observed as `0x00`. Kinds `1` and `4`
  exist in the byte's possible range but have never been triggered or
  seen, and there's no known way to produce them.

None of these block anything `fiedle400` does today (Manual-mode
download/decode works correctly without knowing them) -- this is pure
protocol completeness, parked rather than chased further this cycle.

## Criteria

- [ ] A hypothesis for subframe bytes 3..4 that fits all capture data to
      date, or a documented conclusion that it can't be determined
      without more/different captures
- [ ] `D0` bytes 8..9 and kind byte 1/4: either reproduced once (if a
      way to trigger them is found) or left explicitly as "unknown,
      never observed" in `PROTOCOL.md`
- [ ] `PROTOCOL.md` §3.14 updated with whatever is found
- [ ] Tests pass

## Execution Notes

(Not started.)
