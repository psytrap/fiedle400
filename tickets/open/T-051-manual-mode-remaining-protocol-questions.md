# T-051: Manual-mode protocol -- remaining open questions

- **Status:** Open
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `PROTOCOL.md` §3.2, §3.14 (Manual-mode frames and the `0xEC` header)
  - `fiedle400/protocol/manual.py`

---

## Description & Context

Split out of `tickets/INDEX.md`'s "Open questions" list, where these sat
without a ticket of their own. Distinct from T-047's G9 (which only checks
one Manual-mode recording's `sessions`/`download` output against SpO2
Assistant) -- these are specific decode questions that need a *particular*
kind of real-device capture, not just any recording:

- **Manual-mode sample timing.** `fiedle400` reads one sample per second
  (the header count, as `SpO2.exe` does). A recording timed with a
  stopwatch would confirm it. `PROTOCOL.md` §3.14.
- **Manual-mode unknown bytes.** Subframe bytes 3..4 (`08 7E` SpO2,
  `04 7E` Pulse in the data subframe), `D0` bytes 8..9, and `D0` kinds 1
  and 4 (only kind 0 seen so far). `PROTOCOL.md` §3.14.
- **`0xEC` byte 1, bits 0..3.** `0` in every capture so far; `SpO2.exe`
  compares it with 1 to pick a download path, meaning unknown.
  `PROTOCOL.md` §3.2.

What is NOT known:
- Whether a recording that exercises `D0` kinds 1/4, or a non-zero `0xEC`
  bits 0..3, is even producible on this hardware, or needs a specific
  device state/mode never tried.

---

## Criteria

- [ ] Manual-mode sample timing confirmed (or contradicted) with a
      stopwatch-timed recording.
- [ ] Subframe bytes 3..4 and `D0` bytes 8..9 decoded, or recorded as
      still unknown with what was tried.
- [ ] `D0` kinds 1 and 4 captured at least once, or recorded as not
      reproducible on this hardware.
- [ ] `0xEC` byte 1 bits 0..3 decoded, or recorded as still unknown.
- [ ] `PROTOCOL.md` updated with whatever is settled.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
