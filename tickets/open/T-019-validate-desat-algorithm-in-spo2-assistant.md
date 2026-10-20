# T-019: Validate the decoded desaturation algorithm in SpO2 Assistant

- **Status:** Open
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `scripts/make_desat_probe.py` (writes the probe recording and the predictions)
  - `SPO2_FORMAT.md` §7 (the hypothesis being validated)
  - `tickets/done/2026-W43/T-017-desaturation-and-basal-spo2-definitions.md`

---

## Description & Context

T-017 decoded SpO2 Assistant's desaturation detector and report values from
`SpO2.exe` and the manual (`SPO2_FORMAT.md` §7). That is a hypothesis from
static analysis; no real report was available to check it against. This
ticket checks it by opening a synthetic recording in the real program and
comparing its report with the predictions. T-018 (implementation) should not
start before this is done.

`python3 scripts/make_desat_probe.py OUTDIR` writes:
- `probe-desat.SpO2`: 43.5 min, 1 Hz, start 2026-10-20 22:00:00, SpO2 at
  97 % with 14 cases A-N separated by 120 s, pulse constant 70 bpm.
- `probe-desat.csv`: the same series.
- `expected.json`: the predicted report values and, per case, whether an
  event is predicted.

Predicted with default parameters (drop 4 %, min duration 10 s, criteria
88 %): Total Event 7 (cases A, D, F, H, J, M, N), Index 9.65/hr, Basal SpO2
95.39 %, Avg. Low SpO2 88.71 %, Time <88% 172 s (2.9 min), one artifact
sample (case L). With drop = 3: 8 events; with min duration = 8: 9 events;
with both: 10.

Note: the probe is written by `fiedle400`'s exporter, so it also checks
that SpO2 Assistant opens a `fiedle400` file at all (overlaps with T-011).

---

## Criteria

- [ ] `probe-desat.SpO2` opened in SpO2 Assistant with default analysis
      parameters; the report (PDF or screenshot) is saved with this ticket.
- [ ] Total Event, Index, Basal SpO2, Avg. Low SpO2, Time <88% and
      Artifact % compared with `expected.json`; every difference listed.
- [ ] Event markers checked case by case (A-N) where the program shows
      them.
- [ ] The run repeated with drop = 3 and with min duration = 8, and the
      event counts compared.
- [ ] `SPO2_FORMAT.md` §7 corrected for any difference, or marked as
      validated.

---

## Execution Notes

<!-- Filled in on completion -->
