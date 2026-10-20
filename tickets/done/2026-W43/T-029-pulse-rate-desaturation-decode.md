# T-029: Decode and validate the pulse-rate desaturation detector

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local artifact
    -- same static-analysis target as T-017)
  - `SPO2_FORMAT.md` §7.2 (documents "Pulse change / time ... Pulse-rate
    event parameters; that detector was not decoded" -- the SpO2-side
    decode in the same section, `0x535430`/`0x535710`/`0x535df0` and
    neighbors, is the natural place to look for the pulse equivalent)
  - `scripts/make_desat_probe.py` (T-019's probe-generation method, to be
    extended with a pulse-rate excursion once there's an algorithm to
    predict against)
  - SpO2 Assistant's "Analyseparameter" dialog, Pulsrate Parameter section
    (captured live for T-019, re-confirmed this session against the same
    probe file: Pulsaenderung fuer Ereignis 6 bpm default range 2-20,
    Minimum Ereignisdauer 8 s)

---

## Description & Context

**Split 2026-10-20 out of T-028**, which bundled decode+validate with
implementation. They're separable the same way T-017 (decode) and T-019
(validate) were separate from T-018 (implement) for the SpO2 side; this
ticket is the decode-and-validate half only. [T-030](T-030-pulse-rate-desaturation-implementation.md)
is the implementation half, blocked on this one.

SpO2 Assistant's real Analyseparameter dialog has a "Pulsrate Parameter"
section (pulse change in bpm, minimum duration) alongside the SpO2
desaturation settings T-017 already decoded. The pulse-rate side has never
been decoded: `desat.py`'s own docstring, T-018's "Not done" list, and
T-025's closing notes all independently flag the same gap. T-025 added a
disabled, explicitly-labelled-dummy pair of pulse-rate inputs to the viewer
this session (`#pulseDropBpm`/`#pulseMinDur`) purely so the layout could be
reviewed ahead of time -- they do nothing and must stay that way until this
ticket (and T-030) land.

**What this ticket is:**

1. Static analysis of `SpO2.exe` (same method as T-017: `strings`,
   disassembly around the relevant string/constant references) to find
   the pulse-event acceptance algorithm -- baseline method, merge logic,
   acceptance formula -- and write it up with the same sourcing standard
   as `SPO2_FORMAT.md` §7.2 (disassembly addresses, not guesses).
2. A probe-recording validation step (T-019's own method: a synthetic
   file with known pulse-rate excursions and predicted report values,
   opened in the real SpO2 Assistant on the Windows 8.1 laptop,
   `192.168.2.165`) before trusting the decode. `desat.py`'s SpO2 analogue
   (`detect_events`/`summarize`) and `tests/test_desat.py` are the
   reference shape for what "validated" means here -- real numbers from
   the real program, not just a plausible-looking disassembly.

This ticket's deliverable is the decoded algorithm plus validation
evidence, written into `SPO2_FORMAT.md` and this ticket's Execution Notes
-- not working code in `desat.py` or the viewer (that's T-030).

---

## Criteria

- [x] Pulse-rate event detection algorithm decoded from `SpO2.exe`,
      written up with disassembly addresses, not guesses.
- [ ] Decode validated against the real SpO2 Assistant with a probe
      recording (T-019-style: predicted vs. actual report values), not
      trusted on static analysis alone. *(Moved to
      [T-035](../../open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md)
      (Local): the probe and its predictions are ready, the real program is only on the
      Windows laptop.)*
- [x] `SPO2_FORMAT.md` §7.2 updated to document the pulse-rate algorithm
      alongside the SpO2 one, removing the current "not decoded" note. *(New §7.3.)*
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy, static analysis of `archive/bruteforce/SpO2.exe` with
capstone; image base `0x400000`).

**Finding: there is no separate pulse detector.** `0x532b39`-`0x532c20` builds a second
instance of the SpO2 detector class (constructor `0x533300`, 7 values; run `0x5350a0`, detection
`0x535430`, merging `0x535710`, acceptance `0x535df0`/`0x535f60`) on the pulse channel (sample
buffer `+0x14`; SpO2 is `+4`) and stores the result in the pulse event list `+0xa4`. Its values:
drop = pulse change `[+0xc4]` (default 6, set at `0x531eb0`/`0x532175`), hi = 254 (`push 0xfe`),
lo = 0, max_time 180, min_time = pulse time `[+0xc8]` (default 8, `0x531ebd`/`0x532182`),
max_avg 2, oscillation 1. All comparisons in the detector read these fields, none is a
hard-coded 100. So a pulse event is a **fall** of >= 6 bpm over 8-180 s to the nadir with an
average fall below 2 bpm/s, merged across 1 bpm rebounds; a rise is never one, and the `0xFF`
sentinel breaks it. The pulse list feeds the pulse columns of the report XML
(`0x4fd8e1`-`0x4fdb63`: count, total and average duration, index, adjusted index, artifact %).
Written up in `SPO2_FORMAT.md` §7.3; the parameter row in §7.2 now cites the init addresses.

Code: `fiedle400/desat.py` got `detect_pulse_events` (the existing detector with the pulse
values; `detect_events` unchanged), because the probe's predictions need it. Nothing shows pulse
events yet; that stays T-030, which now waits on T-035's real-program check.

Validation: `scripts/make_pulse_basal_probe.py` writes a probe with ten pulse cases (fall, too
small, too short, boundary, steep-but-accepted, too steep, a rise, too long, merged, split by
probe-out) and predicts 4 pulse events with defaults, 5 with pulse change 5, 5 with pulse time 7.
Running it in the real SpO2 Assistant is [T-035](../../open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md)
(psytrap's request, Local). Tests: `tests/test_desat.py` gained pulse cases (fall vs. rise,
values above 100, parameters, probe-out as None and 255) and a probe check; whole suite green.
