# T-021: Broader real SpO2 Assistant `.spo2` decode coverage

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/plot.py` (`read_spo2_file`, the shipped reader)
  - `archive/capture/raw/`, `archive/capture/realtime/` (existing real
    captures not yet exercised)
  - `tickets/done/2026-W43/T-011-spo2-assistant-interop-check.md` (this
    ticket's own scope was one capture per direction; that's done)

---

## Description & Context

T-011 verified `fiedle400` <-> real SpO2 Assistant compatibility in both
directions by execution, but with the minimum needed to meet its own
criteria: one real device-downloaded file for the write direction, one
capture (`archive/capture/_user_1_0_..._joint.SpO2`) for the read direction.
That's settled and not in question.

This ticket is for broader coverage, deliberately deferred rather than
blocking T-011's close:

- The other existing real captures in `archive/capture/raw/` and
  `archive/capture/realtime/` haven't been round-tripped through
  `fiedle400/plot.py`'s `read_spo2_file` yet -- different capture modes
  (raw vs. realtime vs. joint) might expose a decode difference the one
  `joint.SpO2` file tested didn't.
- Longer real recordings (the one read-direction test was ~3h11m; nothing
  near the file-size/sample-count extremes has been tried).
- A recording containing real finger-out/probe-out data -- T1's own
  "no real finger-out recording exists yet" gap applies here too, and a
  sentinel-heavy real capture would be a more thorough read-direction test
  than the mostly-valid data checked so far.
- More real multi-session downloads through SpO2 Assistant now that T-020's
  gap-fill is in place, beyond the one case already checked.

Not urgent, not blocking anything else -- opened to hold the idea rather
than lose it, per T-011's own note that this coverage was consciously left
out of its scope.

---

## Criteria

- [ ] `archive/capture/raw/` and `archive/capture/realtime/` captures
      decoded with `read_spo2_file`, results compared for plausibility
      (no garbage values, timestamp span matches sample count).
- [ ] At least one further round-trip through the real SpO2 Assistant
      (write or read direction) beyond what T-011 already covered.
- [ ] Any new discrepancy found is written up and either fixed (new
      ticket) or documented in `SPO2_FORMAT.md`, same standard as T-011.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
