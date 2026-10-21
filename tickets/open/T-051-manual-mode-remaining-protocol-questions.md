# T-051: Local inspection -- G7 visual confirmation and Manual-mode protocol questions

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `output/g7-check/rc.html` (already downloaded, see below)
  - `PROTOCOL.md` §3.2, §3.14 (Manual-mode frames and the `0xEC` header)
  - `fiedle400/protocol/manual.py`

---

## Description & Context

Grouped together because both halves need psytrap to physically look at
something, not just run a command -- tracked in addition to
[T-047](T-047-release-v0-4.md), not folded into it.

**1. G7 visual confirmation (T-047's technical half already done).**
Session 1 (160 records, 0 sequence gaps) downloaded in all four formats to
`output/g7-check/`: `rc.html`, `rc.spo2`, `rc.csv`, `rc.json`. The CSV
pre-check: SpO2 94-99% (avg 96.9), HR 63-86 bpm (avg 73.7), 0 probe-out
samples -- same shape as the 0.3.9 cycle's G7 data, no
`.agents/rules/implausible_data_warning.md` pattern. What's missing is
psytrap opening `fiedle400 view output/g7-check/rc.html` and confirming
the chart itself looks physiologically plausible -- that confirmation is
what actually satisfies G7 (`RELEASE_PLAN.md` §2), not the technical
export alone.

**2. Manual-mode protocol -- remaining open questions.** Split out of
`tickets/INDEX.md`'s "Open questions" list. Distinct from T-047's G9
(which only checks one Manual-mode recording's `sessions`/`download`
output against SpO2 Assistant) -- these need a *particular* kind of
real-device capture, not just any recording:

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

- [ ] G7: `fiedle400 view output/g7-check/rc.html` opened; psytrap
      confirms the chart looks physiologically plausible
- [ ] Manual-mode sample timing confirmed (or contradicted) with a
      stopwatch-timed recording
- [ ] Subframe bytes 3..4 and `D0` bytes 8..9 decoded, or recorded as
      still unknown with what was tried
- [ ] `D0` kinds 1 and 4 captured at least once, or recorded as not
      reproducible on this hardware
- [ ] `0xEC` byte 1 bits 0..3 decoded, or recorded as still unknown
- [ ] `PROTOCOL.md` updated with whatever is settled
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
