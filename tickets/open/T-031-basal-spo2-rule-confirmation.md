# T-031: Confirm the exact Basal SpO2 calculation rule

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local artifact
    -- same static-analysis target as T-017)
  - `fiedle400/desat.py` (`summarize()`, `basal_spo2` -- currently "mean
    outside the event falls", explicitly labelled an estimate)
  - `fiedle400/spo2_viewer.py` (the "Basal SpO2 (estimate)" stats row,
    same caveat text)
  - `SPO2_FORMAT.md` §7.1 (Basal SpO2 row) and the T-019 validation
    writeup it references

---

## Description & Context

Basal SpO2 is the one report value T-019's three real-SpO2-Assistant runs
did **not** match exactly -- the real program reported +0.8 pts higher
than predicted every time (`SPO2_FORMAT.md` §7.1/§7.2). Two candidate
rules fit the single data point equally well and neither has been
confirmed by disassembly:

- `fiedle400/desat.py`'s current rule: mean of valid SpO2 samples outside
  any detected event's fall-to-nadir range (96.23% on the T-019 probe).
- The alternative noted in `SPO2_FORMAT.md`: mean of samples >= the
  criteria level, 88% (96.21% on the same probe) -- numerically almost
  identical here, so this probe recording cannot distinguish the two
  rules; a probe designed to make them diverge would be needed.

Both the viewer and `desat.py` already say "estimate"/"not confirmed" out
loud rather than asserting a decoded fact -- this ticket is to actually
resolve it, the same decode-then-validate process T-017/T-019 used for
the desaturation-event algorithm itself:

1. Static analysis of `SpO2.exe` (`strings`, disassembly around the Basal
   SpO2 computation -- likely near the same report-value code region
   `SPO2_FORMAT.md` §7.1 already cites for the other report fields) to
   find the actual averaging rule.
2. A probe recording specifically designed so the two candidate rules
   (outside-event-falls vs. below-criteria) predict different numbers --
   today's T-019 probe doesn't, which is why the ambiguity survived that
   validation pass. Opened in the real SpO2 Assistant on the Windows 8.1
   laptop (`192.168.2.165`) to see which prediction it matches.
3. `fiedle400/desat.py`'s `basal_spo2` updated to the confirmed rule (or
   left as-is with a disassembly citation, if it turns out to already be
   correct), and the "estimate"/"not confirmed" wording removed from both
   `desat.py` and the viewer once it is.

---

## Criteria

- [ ] Basal SpO2's exact averaging rule decoded from `SpO2.exe`, written
      up with disassembly addresses, not guesses.
- [ ] A probe recording where the candidate rules diverge, validated
      against the real SpO2 Assistant, confirming which rule it actually
      uses.
- [ ] `fiedle400/desat.py`'s `basal_spo2` matches the confirmed rule.
- [ ] "(estimate)" / "not confirmed" wording removed from
      `fiedle400/spo2_viewer.py`'s stats row and `desat.py`'s docstring
      once confirmed (or left in place with a one-line note if the
      decode effort is inconclusive).
- [ ] `SPO2_FORMAT.md` §7.1 updated to mark Basal SpO2 as confirmed
      (or document why it stayed inferred).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
