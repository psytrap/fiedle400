# T-004: Synchronize SpO2/Pulse sentinels in `.spo2` export

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local or Cloud
- **Scope & Relevant Files:**
  - `fiedle400/export.py`
  - `SPO2_FORMAT.md`
  - `tests/test_export_spo2.py`

---

## Description & Context

Found while double-checking `SPO2_FORMAT.md` against OSCAR's actual
source (2026-10-19, `gitlab.com/CPAPreporter/oscar-code`,
`CMS50F37Loader::readSpoRFile` in `cms50f37_loader.cpp`), not just its
own description. Full writeup: `SPO2_FORMAT.md` §5.

OSCAR only recognizes a record as probe-out when **both** bytes match
exactly: `o2 == 0x7f && pr == 0xff`. It does not treat either sentinel
independently -- a record with only one channel invalid is imported as
a literal value on that channel (e.g. SpO2 `127%` plotted as a real
reading), not blanked.

`fiedle400/export.py` (lines 94-95) computes `s_byte` and `h_byte` on
independent per-channel conditions:

```python
s_byte = int(spo2) if (spo2 is not None and 1 <= int(spo2) <= 100) else SPO2_INVALID_SPO2
h_byte = int(hr) if (hr is not None and 1 <= int(hr) <= 250) else SPO2_INVALID_HR
```

So a mixed record (one channel sentinel, the other a real value) is
possible in principle: if `spo2` is `None`/out-of-range while `hr` is a
real decoded value, the written bytes are `(0x7F, <real hr byte>)` --
which OSCAR's AND-check does **not** recognize as probe-out, so it
would import `127%` SpO2 as a literal point on the chart.

**Not yet observed in any real capture** -- every real session
downloaded so far has had `flags=ok` throughout (T1, same open
question as the finger-out path). This is a latent risk found by
cross-checking the consumer's actual logic, not a reproduced bug.

## Possible fix (not decided -- pick one when executing)

- Synchronize both bytes to the sentinel pair whenever *either* channel
  is invalid, so `fiedle400`'s own output always matches OSCAR's
  AND-check exactly: if `spo2 is None or hr is None` (or out of range),
  write `(0x7F, 0xFF)` for both, never a mixed pair.
- Or: confirm whether the underlying decoder (`engine/detector.py`,
  `protocol/decompression.py`) can even *produce* a mixed state for the
  storage path (both channels are measured together per T1's own
  finding -- "whole-`0x7F` sentinel subframes line up at the same
  positions in both streams" -- so a mixed state may already be
  structurally impossible upstream, making this a defensive fix rather
  than a correctness fix for data seen so far).

---

## Criteria

- [ ] Decide and document which case this actually is (defensive
      hardening vs. a reachable bug) before choosing the fix shape.
- [ ] `fiedle400`'s own `.spo2` output can never produce a mixed
      sentinel pair, regardless of upstream state.
- [ ] A test exercises the specific case OSCAR's AND-check would
      otherwise misread (one channel invalid, the other a real value).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
