# T-028: Decode and implement pulse-rate desaturation events

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local artifact
    -- same static-analysis target as T-017)
  - `fiedle400/desat.py` (SpO2-side detector to mirror; `DROP`/`MIN_TIME`/
    etc. constants)
  - `fiedle400/spo2_viewer.py` (T-025's SpO2 parameter inputs --
    `#dropPct`/`#minDur`/`#critLevel` -- the pattern a pulse-side panel
    would follow)
  - `SPO2_FORMAT.md` §7.2 (documents "Pulse change / time ... Pulse-rate
    event parameters; that detector was not decoded")

---

## Description & Context

SpO2 Assistant's real Analyseparameter dialog (captured live for T-019)
has a whole second section, "Pulsrate Parameter" (pulse change in bpm,
minimum duration), alongside the SpO2 desaturation settings T-017 decoded
and T-019 validated. The pulse-rate side has never been decoded: `desat.py`
only implements the SpO2 detector, and its own docstring, T-018's "Not
done" list, and T-025's own closing notes all independently flag the same
gap -- there is no pulse-event detection algorithm anywhere in this
project, decoded or otherwise.

T-025 deliberately left pulse-rate parameters out of the viewer's new
adjustable-parameters UI specifically because of this -- a parameter panel
with no real detector behind it would be misleading, not a cosmetic
omission.

**What this ticket is:** the same decode-then-validate process T-017/T-019
already did for the SpO2 side, applied to the pulse-rate detector:

1. Static analysis of `SpO2.exe` (same method as T-017: `strings`,
   disassembly around the relevant string/constant references) to find
   the pulse-event acceptance algorithm -- baseline method, merge logic,
   acceptance formula, matching what `SPO2_FORMAT.md` §7.2 already found
   for the SpO2 side (`0x535430`/`0x535710`/`0x535df0` region and
   neighbors, per that section's own addresses, is the natural place to
   look for the pulse equivalent).
2. A probe-recording validation step (T-019's own method: a synthetic
   file with known pulse-rate excursions, predicted report values, opened
   in the real SpO2 Assistant on the Windows 8.1 laptop) before trusting
   the decode.
3. Implementation in `fiedle400/desat.py` (a pulse-rate counterpart to
   `detect_events`/`summarize`) and the viewer (pulse parameter inputs,
   following T-025's established pattern -- pre-filled from Python-computed
   defaults, live client-side recompute, no hardcoded duplicate values).

**This is a real reverse-engineering effort, not a quick addition.** The
SpO2 side took three separate tickets (T-017 decode, T-019 validate, T-018
implement) plus T-025's later parameter UI. Expect similar scope here, not
a same-day fix.

---

## Criteria

- [ ] Pulse-rate event detection algorithm decoded from `SpO2.exe`,
      written up with the same sourcing standard as `SPO2_FORMAT.md` §7.2
      (disassembly addresses, not guesses).
- [ ] Decode validated against the real SpO2 Assistant with a probe
      recording (T-019-style), not trusted on static analysis alone.
- [ ] `fiedle400/desat.py` implements the pulse-rate detector, with tests
      matching the validated real-program numbers.
- [ ] Viewer gains pulse-rate parameter inputs (pulse change %, min
      duration) following T-025's pattern -- live recompute, defaults from
      Python, no dead/non-functional inputs.
- [ ] `SPO2_FORMAT.md` §7.2 updated to document the pulse-rate algorithm
      alongside the SpO2 one, removing the current "not decoded" note.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
