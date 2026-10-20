# T-036: Reusable procedure for confirming a decoded algorithm in SpO2 Assistant

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `SPO2_ASSISTANT_CHECKS.md` (new)
  - `SPO2_FORMAT.md` §7 (links to it)
  - `tickets/open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md`

---

## Description & Context

psytrap, 2026-10-20: split T-035. Write a reusable document for confirming any decoded
SpO2 Assistant algorithm in the real Windows app, and keep exercising it for T-029/T-031 as
a separate ticket (T-035, Local, deferred). The method so far lived only in T-019's notes.

---

## Criteria

- [x] A procedure document covering: stating the hypothesis, building a probe script with
      boundary cases and asserted predictions, running it in the real program (parameters
      screenshot, report image and XML, one parameter change per run), comparing with the
      printed precision, and recording the outcome in the ticket and `SPO2_FORMAT.md`.
- [x] Linked from `SPO2_FORMAT.md` §7 and from T-035.
- [x] Helpers the procedure needs (psytrap: write them, do not exercise them in the cloud):
      the probe scripts already exist; `scripts/check_spo2_assistant_report.py` compares a
      report XML with `expected.json`.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy). `SPO2_ASSISTANT_CHECKS.md` sits next to
`SPO2_FORMAT.md` (the repo has no `docs/` folder), generalised from T-019's run: the probe
pattern of `make_desat_probe.py` / `make_pulse_basal_probe.py`, the Analyseparameter
screenshot and the `<analy_para>` check before accepting a run (T-019's run 2 lesson), the
XML fields to read, one-decimal comparison, and where results go. It ends with a table of
the checks so far (T-019 validated, T-035 deferred).

Helper: `scripts/check_spo2_assistant_report.py REPORT.xml EXPECTED.json [--variant KEY]`
(stdlib only). The report XML layout comes from the writer's format strings in `SpO2.exe`
(`0x61bb20`-`0x61c444`, writer `0x4fd860`-`0x4fdf58`), since no report XML is in the repo:
the expected.json keys map to `analy_result` paths, `time_below_88_s` is converted to the
report's minutes, and every value is compared at one decimal. It checks the run's
`<analy_para>` against the defaults (or the `--variant`), prints a Markdown table, exits 1 on
a difference and 2 on an unreadable file; a UTF-16 file is accepted in case the program
writes one. Tests: `tests/test_check_spo2_assistant_report.py` (5) on XML built from those
format strings. Not run against a real report: that is the local step (T-035).
