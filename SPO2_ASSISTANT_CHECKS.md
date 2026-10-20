# Confirming a decoded algorithm in the real SpO2 Assistant

A reusable procedure for checking something decoded from `SpO2.exe` (`SPO2_FORMAT.md` §7)
against the real Windows program, the way T-019 did for the desaturation events. Static
analysis gives a hypothesis; this turns it into a validated fact or a documented
difference. Each check gets its own ticket (`Owner: Local`) that links here and fills in the
specifics.

## 1. Before the run (cloud or local)

1. **State the hypothesis** in `SPO2_FORMAT.md`, with disassembly addresses, and mark it as
   not yet checked against the program.
2. **Build a probe script** in `scripts/` (examples: `make_desat_probe.py`,
   `make_pulse_basal_probe.py`). The pattern:
   - a synthetic 1 Hz series with a flat baseline and named cases separated by long flat
     gaps (120 s), so each case is easy to find on the chart;
   - for every rule being tested, at least one case that just passes and one that just
     fails it (a boundary on each side), and where candidate rules exist, a case on which
     they give clearly different numbers at the program's printed precision (usually one
     decimal);
   - predictions computed with fiedle400's own implementation (`fiedle400/desat.py`), with
     each case's expected outcome asserted in the script, so a probe cannot silently
     drift from its design;
   - output: `<name>.SpO2` (written by `export.build_spo2_binary`, so the run also checks
     that the program opens a fiedle400 file), `<name>.csv` with the same series, and
     `expected.json` (summary values, values for changed parameters, per-case outcome).
3. **Pin the predictions in a test** (`tests/test_desat.py`) so they stay reproducible.
4. **Generate the files**: `python3 scripts/<script>.py OUTDIR`. The cloud keeps a copy in
   the project files under `probe-spo2/<ticket>/`.

## 2. The run (local, Windows)

Use the real SpO2 Assistant on the Windows 8.1 laptop (setup and access as in T-011), not Wine
or a VM. Never touch the oximeter for this: the probe is a file, and no device or flash
operation is needed.

1. Copy the probe files to a working folder on the laptop (T-019 used `C:\Users\mik\fiedle400\`).
2. Open `<name>.SpO2` in SpO2 Assistant. If it is rejected, stop: that is an interop finding
   (compare with T-011), not an algorithm finding.
3. Open the **Analyseparameter** dialog and take a screenshot before every run, so the
   parameters of each run are on record (defaults: SpO2 drop 4 %, minimum event duration
   10 s, criteria 88 %; pulse change 6 bpm, minimum duration 8 s).
4. Export the report (**Bericht**): keep both the image and the XML. The XML's
   `<analy_para>` block states the parameters that were really used; check it before
   accepting a run (T-019's second run once re-saved the previous report unchanged).
5. Repeat for every parameter variant listed in `expected.json`, changing one parameter at a
   time.

## 3. Reading and comparing

- Take the numbers from the XML where possible (`<analy_result>`: `<totle>`, `<time>`,
  `<avg>`, `<index>`, `<artifact>`, `<artifact_index>`, `<spo2><basal>`, `<time_low>`,
  `<event_low>`, `<min>`, `<event_min_avg>`, `<event_min_avg_low>`, and the `<pulse>`
  columns), and the labels from the report image. The program prints one decimal, so a
  prediction matches when it rounds to the printed value.
- The report has no per-event list. Check individual cases only as far as the chart allows
  (markers in roughly the right places); say so rather than over-claim.
- Write a table per run: report value, predicted, actual, result. List every difference,
  however small, and whether rounding explains it. `scripts/check_spo2_assistant_report.py`
  does this from the report XML and the probe's `expected.json`, and also checks that the
  run's `<analy_para>` holds the intended parameters:

  ```bash
  python3 scripts/check_spo2_assistant_report.py report.xml expected.json                 # default run
  python3 scripts/check_spo2_assistant_report.py report.xml expected.json --variant drop=3
  ```

  It prints a Markdown table for the ticket and exits 1 on any difference. A prediction that
  has no place in the report (for example a rule the decode ruled out) is not compared; read
  those off the report by hand.

## 4. Recording the outcome

- In the check's ticket: Execution Notes with the tables, the parameters of each run, the
  report files' names and where they are kept (T-019 kept them locally under
  `output/<ticket>-probe/windows-result/`, which is gitignored; commit only what is free of
  personal data).
- In `SPO2_FORMAT.md` §7: mark the hypothesis validated (name the ticket), or correct it and
  say what the program did instead.
- If a prediction was wrong: open a cloud ticket to fix `fiedle400/desat.py` and the viewer's
  JS port together (the parity test, `tests/test_desat_js_parity.py`, keeps them in step),
  and update the probe's assertions.

## Checks so far

| Ticket | What | Probe script | Result |
| :---: | :--- | :--- | :--- |
| T-019 | SpO2 desaturation events (§7.2) | `make_desat_probe.py` | Validated (3 runs); Basal SpO2 differed, later decoded in T-031 |
| T-035 | Pulse-rate events (§7.3), Basal SpO2 rule (§7.1) | `make_pulse_basal_probe.py` | Deferred |
