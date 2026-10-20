# T-020: Multi-session `.spo2` export silently discards the gap between sessions

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/export.py` (`build_spo2_binary`, `export_records`)
  - `SPO2_FORMAT.md` (header's single start-time field; the OSCAR
    timestamp-alignment note this affects)
  - `tickets/open/T-011-spo2-assistant-interop-check.md` (discovered while
    testing this ticket's real-device file against SpO2 Assistant)

---

## Description & Context

Found while working T-011: `fiedle400 download --all --format spo2` was run
against the real device with two stored sessions --

- Session 1: starts 2026-10-16 08:37:31, duration 2m40s (160 records) -> ends 08:40:11
- Session 2: starts 2026-10-16 08:43:12, duration 30s (30 records)

-- a real gap of about 3 minutes (181 s) between them. The combined
`.spo2` file opened in SpO2 Assistant shows **one continuous 3m10s
recording**, because `fiedle400/export.py`'s `build_spo2_binary`
(around `export.py:55`-`83`) assigns record `i` to `start_dt + i` seconds
by **array index**, never consulting each record's own `timestamp` field
after the first one. Every record of every session after the first gets
silently compressed: session 2's 30 records land at file-time
08:40:11-08:40:41, not their true 08:43:12-08:43:42.

This is not an SpO2 Assistant compatibility problem (the file is well-formed
and opens cleanly -- that's T-011's own finding) and not a bug in the
single-session case. It only affects `download --all`/multi-session export,
and it is a real correctness problem for anyone reading the file's
timestamps: `SPO2_FORMAT.md` itself documents that **OSCAR aligns oximetry
data against CPAP flow/pressure data using the header timestamp** -- a
silently compressed file would misalign a real recording against real CPAP
data, by exactly the dropped gap duration, with no indication anything is
wrong.

**Two fix directions, not decided here:**
1. **Preserve wall-clock alignment within one file.** Fill the gap with
   sentinel/invalid samples (the same `(0x7F, 0xFF)` pair already used for
   probe-out, per T-004) so the file's sample count and header start time
   stay honest about elapsed real time. Keeps "download --all = one file"
   but the file grows by the gap length (here, ~181 extra sentinel samples
   for a 3-minute gap -- fine for this case, possibly large for longer
   between-session gaps).
2. **One `.spo2` file per session.** Since the format has no field for
   multiple sessions at all (confirmed in T-011/T-019 work -- it's a single
   header, single start time, flat sample array), arguably concatenating
   unrelated sessions into one file was always the wrong default; write
   `sessionN.spo2` per session instead, same as the vendor's own files are
   one recording each.

Either direction needs to decide what `download --all -f spo2`'s default
*should* mean -- that's a product decision, not something to guess at while
fixing the symptom.

---

## Criteria

- [ ] One of the two directions above (or a third) is chosen and the reason
      recorded here.
- [ ] `fiedle400/export.py` updated so a multi-session `.spo2` export never
      silently misrepresents real elapsed time between sessions.
- [ ] A test with records from two sessions with a real gap between their
      timestamps, asserting the fix (either sentinel-filled duration, or
      one file per session, matching whichever direction was chosen).
- [ ] `SPO2_FORMAT.md` updated if the multi-session behavior changes.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
