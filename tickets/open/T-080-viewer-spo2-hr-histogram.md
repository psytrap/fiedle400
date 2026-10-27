# T-080: SpO2/HR histogram in the HTML viewer

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py`

---

## Description & Context

The vendor's SpO2 Assistant software shows a histogram of time spent at
each SpO2 value and each pulse-rate (HR) value for a session. `fiedle400`'s
HTML viewer has no equivalent -- it only plots the time-series traces.
Add SpO2 and HR distribution histograms to the viewer for parity with
SpO2 Assistant.

Parked alongside the other viewer feature requests (T-056, T-067, T-068,
T-076) until picked up.

**Value:** a time series shows *when* desaturations happened but not how
much of the session was actually spent low -- a histogram makes the
overall burden visible at a glance (e.g. "80% of the night above 95%,
but a long tail down at 85-88%" vs. a few sharp transient dips, which
look similar on a time-series plot but mean very different things
clinically). Same for HR: it separates a session that was mostly steady
with brief spikes from one with sustained tachycardia. It's also the
one view users already know from SpO2 Assistant, so it's the most
direct way to compare a fiedle400-captured session against a prior one
read in the vendor app.

---

## Criteria

- [ ] HTML viewer shows a histogram of time spent per SpO2 value
- [ ] HTML viewer shows a histogram of time spent per HR/pulse-rate value
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

(Not started.)
