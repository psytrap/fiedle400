# T-035: Validate the decoded pulse-rate events and Basal SpO2 rule in SpO2 Assistant

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `SPO2_ASSISTANT_CHECKS.md` (the procedure to follow, written in T-036)
  - `scripts/make_pulse_basal_probe.py` (writes the probe recording and the predictions)
  - `SPO2_FORMAT.md` §7.1 (Basal SpO2 row) and §7.3 (pulse-rate events), the hypotheses
    being validated
  - `tickets/done/2026-W43/T-029-pulse-rate-desaturation-decode.md`,
    `tickets/done/2026-W43/T-031-basal-spo2-rule-confirmation.md` (the decodes)
  - `fiedle400/desaturation.py` (`detect_pulse_events`, `summarize`'s `basal_spo2`)

---

## Description & Context

**Deferred by psytrap, 2026-10-20.** T-030 was implemented without waiting for this
check, so the viewer shows pulse events from the static decode alone. If this check later
finds a difference, fix `desaturation.py` and the viewer's JS port together (the T-027 parity test
keeps them in step).

psytrap, 2026-10-20: confirm the new findings in the real Windows program once the
analysis is done. T-029 and T-031 decoded two things from `SpO2.exe` (static analysis only,
addresses in `SPO2_FORMAT.md`):

- **Pulse-rate events** are the SpO2 detector run a second time on the pulse series with
  pulse change 6 bpm, minimum time 8 s, valid range 0..254, max 180 s, max average fall
  2 bpm/s, oscillation 1. Only **falls** in pulse rate are events, never rises.
- **Basal SpO2** is the mean of the valid SpO2 samples outside every event's descent
  (start to nadir). That is the rule `desaturation.py` already used; T-019's single data point
  (96.2 reported) could not tell it apart from "mean of samples >= 88 %".

Follow `SPO2_ASSISTANT_CHECKS.md` (the reusable procedure split out of this ticket into
T-036). `python3 scripts/make_pulse_basal_probe.py OUTDIR` writes
`probe-pulse-basal.SpO2` (49.5 min, 1 Hz, start 2026-10-21 22:00:00), `probe-pulse-basal.csv`
(the same series) and `expected.json` (predictions overall and per case). A copy generated
in the cloud is in the project files under `probe-spo2/t035/`.

Predicted with default parameters (SpO2 drop 4 %, min 10 s, criteria 88 %; pulse change
6 bpm, time 8 s):

| Report value | Predicted | If the decode is wrong |
| :--- | :---: | :--- |
| SpO2 Total Event | 2 (cases S1, S2) | |
| Basal SpO2 | **94.3** | 96.8 = mean of samples >= 88 %; 93.7 = plain mean |
| Time <88% | 731 s (12.2 min) | |
| Pulse events (total) | **4** (cases P1, P4, P5, P9) | 5+ if the rise (P7) or the long/steep/split cases count |
| Pulse events, pulse change = 5 | 5 (adds P2) | |
| Pulse events, pulse time = 7 | 5 (adds P3) | |
| Pulse index | 4.8 /hr | |
| Pulse average event duration | 9.8 s | |

Cases (SpO2 at 97 %, pulse at 70 bpm, 120 s apart): S1 4 % over 12 s (event); S2 25 % over
175 s (event, left out of Basal); S3 12 % into a 10-minute hold at 85 % (no event, 606 s >
180 s, counted in Basal). P1 -6 bpm/10 s (event); P2 -5 bpm/10 s; P3 -6 bpm/7 s; P4 -6 bpm/8 s
(event); P5 -19 bpm/10 s (event); P6 -20 bpm/10 s (too steep); P7 +10 bpm rise; P8 -8 bpm
over 200 s; P9 -3, +1, -5 bpm (merged, event); P10 -3 and -4 bpm split by a probe-out second.

What is NOT known: which report rows show the pulse values (the report XML has pulse
columns for event count, time, average duration, index, adjusted index and artifact %,
`0x4fd8e1`-`0x4fdb63`), and whether the UI labels them as events. Never erase device
flash for this; it only needs the laptop and the probe file.

---

## Criteria

- [ ] `probe-pulse-basal.SpO2` opened in SpO2 Assistant with default parameters; the report
      (PDF or screenshot) saved with this ticket.
- [ ] Basal SpO2 compared with 94.3 / 96.8 / 93.7; which rule matched is recorded.
- [ ] Pulse event count (and index / average duration where shown) compared with
      `expected.json`; every difference listed.
- [ ] Re-run with pulse change = 5 and with pulse time = 7; counts compared (5 and 5)
      (`scripts/check_spo2_assistant_report.py report.xml expected.json --variant "pulse change=5"`).
- [ ] `SPO2_FORMAT.md` §7.1 / §7.3 marked as validated, or corrected; `desaturation.py` fixed if
      a prediction was wrong (cloud follow-up if needed).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
