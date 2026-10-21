# T-045: Pulse row reads the wrong channel's max_time; a sentinel-index quirk is shared by both implementations

- **Status:** Open
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the pulse-events stats row; `_detect`'s port)
  - `fiedle400/desat.py` (`_detect`)
  - `tests/test_desat_js_parity.py` (why the parity harness can't catch the
    second item)

---

## Description & Context

Two small findings from T-032's review, logged there but not promoted to
its own criteria since neither is currently visible-wrong. Recorded here so
they are not lost.

**1. The pulse-events display row reads the SpO2 channel's `max_time`.**
`spo2_viewer.py`'s `stats()` builds the "Pulse-rate events" row as
`pp.drop + ' bpm over ' + pp.min_time + '-' + analysis.params.max_time + ' s'`
-- `analysis.params` is the *SpO2* channel's parameters, not
`analysis.pulse.params`. Harmless today because both channels fix
`max_time` at 180, but it is a latent cross-channel bug: if the two ever
diverge (e.g. a future ticket makes `max_time` adjustable per channel), the
pulse row would silently show the SpO2 value.

**2. `desat.py`'s `_detect` has a sentinel-index quirk, ported identically
into the JS.** `st` (a candidate's start index) is tested for truthiness
(`if st:` / `if (st)`), and `0` is a legitimate sample index. A candidate
that opens exactly at index `0` -- only reachable when the fall happens at
`i == 1`, since index `0` itself is never compared to anything -- sets
`st = 0`, which then reads as "no candidate open" on the very next
iteration's truthiness check. A descent starting at the first sample of a
series could therefore fail to extend/merge correctly. Nothing in
`SPO2_FORMAT.md` §7.2 says the vendor has the same behaviour -- it has no
`[X]`/`[M]` source, it's purely a side effect of the sentinel choice.
Because `fiedle400/spo2_viewer.py`'s JS is a hand port of the same logic,
it has the identical `st = 0, en = 0` quirk, so T-027's parity harness
(`test_desat_js_parity.py`) compares two implementations that share the bug
and can never flag it -- parity against each other proves nothing about
whether either matches the real device here.

What is NOT known:
- Whether the real device/vendor program can ever produce a recording
  whose first sample is the start of a descent (the only way to trigger
  the sentinel-index quirk), or whether this is purely theoretical.
- Whether the pulse `max_time` divergence will ever actually happen, or
  this is defensive-only.

---

## Criteria

- [ ] The pulse-events row reads `analysis.pulse.params.max_time` (or the
      pulse channel's own data, however that's named after the fix), not
      the SpO2 channel's.
- [ ] A test fails without that fix (e.g. give the two channels different
      `max_time` values and check the pulse row reflects its own).
- [ ] A decision on the sentinel-index quirk: fix it (e.g. a dedicated
      "no candidate open" sentinel distinct from a valid index `0`, in
      both `desat.py` and the JS port, with a test covering a descent
      starting at sample index 0), or record why it's left as-is -- not
      silently carried forward unaddressed.
- [ ] If fixed, note whether it changes any existing recording's event
      count (it shouldn't for any recording that doesn't start mid-descent
      at sample 0).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
