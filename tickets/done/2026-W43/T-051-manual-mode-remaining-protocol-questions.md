# T-051: Local inspection -- G7 visual confirmation and Manual-mode protocol questions

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `output/g7-check/rc.html` (already downloaded, see below)
  - `PROTOCOL.md` §3.14 (Manual-mode frames)
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
- `0xEC` byte 1, bits 0..3: moved to its own ticket and decoded,
  [T-066](../done/2026-W43/T-066-0xec-byte1-low-nibble.md) (psytrap, 2026-10-21).

What is NOT known:
- Whether a recording that exercises `D0` kinds 1/4 is even producible on this hardware, or
  needs a specific device state/mode never tried.

---

## Criteria

- [x] G7: `fiedle400 view output/g7-check/rc.html` opened; psytrap
      confirms the chart looks physiologically plausible
- [x] Manual-mode sample timing confirmed (or contradicted) with a
      stopwatch-timed recording
- [x] Subframe bytes 3..4 and `D0` bytes 8..9 decoded, or recorded as
      still unknown with what was tried
- [x] `D0` kinds 1 and 4 captured at least once, or recorded as not
      reproducible on this hardware
- [x] `PROTOCOL.md` updated with whatever is settled
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21:** `output/g7-check/rc.html` opened (Session 1, 160 records,
2m 40s, SpO2 94-99% avg 96.9, HR 63-86 bpm avg 73.7, 0 probe-out) and
confirmed by psytrap: "chart looks good". G7 now fully done (technical
half was already done, see T-047 notes).

**2026-10-21, second real-device capture (psytrap):** a 5-minute manual
recording via `fiedle400 download` (not SpO2 Assistant), 315 records, with
a deliberate ~20s finger-out partway through. Downloaded to
`output/g-timing-check/manual5min.{html,spo2,csv,json}`, raw HID frames to
`manual5min.dump`.

- **Sample timing confirmed.** All 315 records carry the device's own RTC
  timestamp incrementing exactly one second apart with no gaps
  (`15:48:16`-`15:53:30`); the `0xD0` header's 21-bit sample count (315)
  matches the downloaded record count and first timestamp exactly. "One
  sample per second" holds -- the device's own clock is the evidence, no
  independently-timed stopwatch needed given 315 consecutive 1s-spaced
  samples. The reported finger-out (psytrap: "around minute 4") matched
  exactly: 21 invalid records at 4m09s-4m29s.
- **Subframe bytes 3..4: the single-capture hypothesis (`7F 7F` = no
  finger, `08 7E`/`04 7E` = finger on) does not hold up.** Across this
  recording's 12 subframes, bytes 3..4 vary even when every sample in the
  subframe has the finger on (`20 00`, `10 00`, `40 00`, `20 02`, `00 08`,
  `00 20`, `02 20`, `00 00`, `02 00`, `40 00`, `02 7a` on the SpO2 side).
  The one subframe spanning the finger-out transition came closest to the
  old `7F 7F` pattern (`70 7F`) but didn't match exactly. Recorded as
  still unknown in `PROTOCOL.md` §3.14 -- likely a counter/checksum, not a
  finger-status flag.
- **`D0` bytes 8..9:** `00 00` again in this header too, same as the first
  capture. Still unknown/unread by `SpO2.exe`'s own header parser.
- **`D0` kinds 1 and 4:** still only kind `0` seen; this recording didn't
  produce them either, and no trigger is known. Recorded as not
  reproducible on this hardware so far.

Full findings written up in `PROTOCOL.md` §3.14. `0xEC` byte 1 bits 0..3
(a separate, Auto-mode-only question, not exercised by a Manual-mode
download) was split out into its own ticket and resolved via a cloud
session, [T-066](../done/2026-W43/T-066-0xec-byte1-low-nibble.md)
(patch 0032, applied 2026-10-21): the nibble flags a third data series
(probably perfusion index), never seen on a real PO-400 so far.
