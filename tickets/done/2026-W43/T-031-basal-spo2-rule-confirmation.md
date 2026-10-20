# T-031: Confirm the exact Basal SpO2 calculation rule

- **Status:** Done
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

- [x] Basal SpO2's exact averaging rule decoded from `SpO2.exe`, written
      up with disassembly addresses, not guesses.
- [ ] A probe recording where the candidate rules diverge, validated
      against the real SpO2 Assistant, confirming which rule it actually
      uses. *(Probe built, predictions 94.3 / 96.8 / 93.7; the real-program run moved to
      [T-035](../../open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md), Local.)*
- [x] `fiedle400/desat.py`'s `basal_spo2` matches the confirmed rule.
- [x] "(estimate)" / "not confirmed" wording removed from
      `fiedle400/spo2_viewer.py`'s stats row and `desat.py`'s docstring
      once confirmed (or left in place with a one-line note if the
      decode effort is inconclusive).
- [x] `SPO2_FORMAT.md` §7.1 updated to mark Basal SpO2 as confirmed
      (or document why it stayed inferred).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy, static analysis of `archive/bruteforce/SpO2.exe`).

**Decoded rule:** Basal SpO2 = (sum of valid SpO2 samples - sum of the samples from each SpO2
event's start to its nadir) / (valid count - number of those samples), printed `%3.1f`; not
computed when the count is 0. Path: the XML writer prints `<basal>%3.1f</basal>` at `0x4fdbcd`
from the report object's double at `+0x50` (getter `0x468a30`, object singleton at `0x6368f8`).
That field is written once, at `0x54d059`, in the report builder `0x54c93b`:
- `0x54cee2`-`0x54cf80`: over the SpO2 value/count list (`+0x74`), skipping value `0x7F`
  (`0x468920`), sum += value x count and n += count;
- `0x54cf82`-`0x54d033`: over the SpO2 event list (`+0x94`; elements `start`, `duration`),
  n_ev += duration + 1 and sum_ev += every sample from `start` to `start + duration`
  (`0x4efc20(1)` = SpO2 buffer, `0x517680`);
- `0x54d038`-`0x54d059`: if n - n_ev > 0, basal = (sum - sum_ev) / (n - n_ev).

This is the rule `desat.py` already used ("mean outside the event falls"), so the T-019 value
(96.2 vs. 96.23) is explained, and the "mean of samples >= 88 %" alternative is ruled out by the
code. Changes: `desat.summarize` no longer falls back to the mean of all valid samples when
nothing is left outside events (the program does not compute a value then; we return None),
same in the viewer's JS port (T-027 parity test covers it). The "(estimate)" label and the
"not confirmed" wording are gone from the viewer and `desat.py`; `SPO2_FORMAT.md` §7.1 has
the decode. One small known difference: the program counts a raw 0 as valid, `desat.py` only
1..100 (fiedle400's own files never contain 0).

While there, the report builder also showed how the other values are computed (index =
events x 3600 / samples, artifact % = sentinel count x 100 / samples, adjusted index = events x
3600 / (samples - sentinel count), constants at `0x5b05e8`/`0x5b0558`), which matches §7.1.

Validation on a probe where the rules diverge: `scripts/make_pulse_basal_probe.py` (a long
deep event left out of the decoded mean and a 10-minute hold at 85 % that is no event):
decoded 94.3, ">= 88 %" 96.8, plain mean 93.7. Running it in the real program is
[T-035](../../open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md) (Local).
