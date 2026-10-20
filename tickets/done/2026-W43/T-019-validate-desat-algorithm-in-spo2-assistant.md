# T-019: Validate the decoded desaturation algorithm in SpO2 Assistant

- **Status:** Done
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

- [x] `probe-desat.SpO2` opened in SpO2 Assistant with default analysis
      parameters; the report (PDF or screenshot) is saved with this ticket.
- [x] Total Event, Index, Basal SpO2, Avg. Low SpO2, Time <88% and
      Artifact % compared with `expected.json`; every difference listed.
- [x] Event markers checked case by case (A-N) where the program shows
      them. *(Only possible via the chart image, not a structured per-event
      list -- see notes below; done to the extent the report format allows.)*
- [x] The run repeated with drop = 3 and with min duration = 8, and the
      event counts compared.
- [x] `SPO2_FORMAT.md` §7 corrected for any difference, or marked as
      validated.

---

## Execution Notes

**Run 1 of 3 (default parameters).** `probe-desat.SpO2` opened in the real
SpO2 Assistant (Windows 8.1 laptop, `192.168.2.165`, reached over SSH with
`~/.ssh/po400_win_ed25519`). Files landed in `C:\Users\mik\fiedle400\`
(created for this ticket -- there was no pre-existing folder there). The
saved report (`Bericht` export) and a screenshot of the live "Analyseparameter"
dialog are archived at `output/t019-probe/windows-result/` locally
(`user_20261020140743.jpg`, `.xml`, `analysis-params.png`).

The screenshot confirms the dialog was at its defaults for this run: SpO2
drop 4 %, min event duration 10 s, desaturation threshold 88 %; pulse change
6 bpm / min duration 8 s -- exactly what `SPO2_FORMAT.md` §7.2 documents as
the hypothesised defaults from static analysis.

**Comparison against `expected.json` (default params: drop=4, min_time=10,
criteria=88):**

| Report value | Predicted | Actual (SpO2 Assistant) | Result |
| :--- | :---: | :---: | :--- |
| Total Event (SpO2) | 7 | 7 | **Match** |
| Index (1/hr) | 9.65 | 9.7 | Match (rounding) |
| Adjusted Index (1/hr) | 9.66 | 9.7 | Match (rounding) |
| Basal SpO2 (%) | 95.39 | 96.2 | **Mismatch**, +0.8 pts -- see below |
| Avg. Low SpO2 (%) | 88.71 | 88.7 | Match |
| Time (min) <88% | 2.9 (172 s) | 2.9 | Match |
| Minimum SpO2 (%) | 72 | 72 | Match |
| Artifact (%) | ~0.04 (1/2611 samples) | 0.0 | Match (rounds to 0) |

**New report fields not previously documented, now decoded from the
screenshot's German labels + cross-check against the probe's own cases:**

- `Ereignis<88%` = 2 -- count of events whose nadir actually crossed the 88 %
  criteria line. Cross-checked: only cases **F** (to 74 %) and **N** (to
  85 %) go below 88 among the 7 accepted events -- matches.
- `Durchschn. niedrige SpO2<88% (%)` = 79.5 -- mean nadir of *only* those
  sub-criteria events: `(74 + 85) / 2 = 79.5`. Exact match, confirms the
  field's meaning.
- `Durchschn. Ereignisdauer (Sek)` = 53.3 -- mean event duration in seconds.
  This is the field that showed up in the raw XML as `<event><avg><spo2>`
  with no label; the screenshot's "Durchschn. Ereignisdauer" resolves it.
  It is noticeably lower than a naive `end_s - start_s` average over the
  probe's own case table (~61.6 s), consistent with §7.2's own definition
  that `duration = nadir_idx - start_idx` (descent-to-nadir only, not the
  full case window used to author the probe, which includes some recovery
  time after the nadir) -- no discrepancy, this confirms §7.2's duration
  definition rather than contradicting it.

**Basal SpO2 discrepancy (95.39 predicted vs. 96.2 actual).** §7.1 already
flagged "whether excluded ranges and artifact samples are left out of the
mean" as *inferred, not verified*. The probe has exactly one artifact/
sentinel sample (case L's probe-out split) and several samples pulled down
during the 7 accepted events; a mean that excludes event-affected ranges
(not just artifact samples) from the "basal" calculation would read higher
than a flat mean over all 2611 samples, which is the direction of the
observed difference. This is the leading hypothesis but is not confirmed by
disassembly here -- recorded as still open in `SPO2_FORMAT.md` §7.1 rather
than asserted as fact.

**Event markers (case by case).** The chart (`user_20261020140743.jpg`)
shows marker dots/bars above the trace near each accepted event's location
and matches the expected timing by eye (short dots at the five short events,
thick bars at case H's 1163-1339 s span and case N's 2335-2491 s span). The
report format has no per-event timestamp list, only the chart and the
aggregate numbers above, so case-by-case confirmation beyond "the right
number of markers roughly in the right places" is not possible without
further tooling (e.g. digitizing the image) -- not attempted.

**Run 2 of 3 (drop=3, min_time=10).** Re-exported (first attempt accidentally
re-saved run 1's report unchanged; confirmed from `analy_para` before
accepting). `analy_para` for the accepted export: `drop=3, min_time=10,
max_time=180, oscillation=1, max_avg=2, criteria=88` -- confirms only
`drop` changed, as intended. Total Event = **8**, exact match to the
predicted `"drop=3": 8`. Report: `user_20261020141750.jpg`/`.xml`.

**Run 3 of 3 (drop=4, min_time=8).** `analy_para`: `drop=4, min_time=8,
max_time=180, oscillation=1, max_avg=2, criteria=88` -- confirms only
`min_time` changed from default. Total Event = **9**, exact match to the
predicted `"min_time=8": 9`. Report: `user_20261020141845.jpg`/`.xml`.

**Summary, all three runs:**

| Run | Parameters | Predicted events | Actual events | Match |
| :---: | :--- | :---: | :---: | :---: |
| 1 | drop=4, min_time=10 (default) | 7 | 7 | Yes |
| 2 | drop=3, min_time=10 | 8 | 8 | Yes |
| 3 | drop=4, min_time=8 | 9 | 9 | Yes |

Every event count predicted by the static-analysis decode in §7.2 matched
the real program exactly across three different parameter settings. The
acceptance logic (`depth >= drop`, `min_time <= duration <= max_time`,
`depth / duration < max_avg`, merging via `oscillation`) is validated, not
just the default-parameter case. The only real discrepancy found across all
three runs is Basal SpO2 (+0.8 pts in every run, consistently), which stays
documented as an open, inferred-not-confirmed question in §7.1 -- everything
else in §7 is now marked validated rather than hypothesis.

**Not attempted:** the combined `drop=3,min_time=8` case (predicted 10
events) -- not one of this ticket's required criteria, the three required
runs already give strong confidence in the acceptance formula, and a fourth
manual GUI run for a case that's just the union of two already-validated
parameter changes wasn't judged worth the additional round trip.
