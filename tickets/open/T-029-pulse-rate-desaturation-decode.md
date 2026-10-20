# T-029: Decode and validate the pulse-rate desaturation detector

- **Status:** Open
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

- [ ] Pulse-rate event detection algorithm decoded from `SpO2.exe`,
      written up with disassembly addresses, not guesses.
- [ ] Decode validated against the real SpO2 Assistant with a probe
      recording (T-019-style: predicted vs. actual report values), not
      trusted on static analysis alone.
- [ ] `SPO2_FORMAT.md` §7.2 updated to document the pulse-rate algorithm
      alongside the SpO2 one, removing the current "not decoded" note.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
