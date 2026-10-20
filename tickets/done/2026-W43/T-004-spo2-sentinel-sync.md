# T-004: Synchronize SpO2/Pulse sentinels in `.spo2` export

- **Status:** Done
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

- [x] Decide and document which case this actually is (defensive
      hardening vs. a reachable bug) before choosing the fix shape.
- [x] `fiedle400`'s own `.spo2` output can never produce a mixed
      sentinel pair, regardless of upstream state.
- [x] A test exercises the specific case OSCAR's AND-check would
      otherwise misread (one channel invalid, the other a real value).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**Decision: reachable bug, not just defensive hardening.** Traced the
merge path in `fiedle400/engine/device.py`'s `flush_block_buffers`:
`is_probe_out` is derived from whichever of the paired SpO2/pulse
events is present (`flg = s_ev.status_str if s_ev else (h_ev.status_str
if h_ev else "ok")`), checking only *that* event's own status, not
both independently. When `s_ev` exists and reports "ok" but the paired
`h_ev.heart_rate` is `None` with no prior `last_block_hr` to fall back
on (the first record of a session, before any valid heart rate has
been seen), `h_val` stays `None` while `s_val` is a real SpO2 value --
a genuinely mixed record reaches `export.py`, not a hypothetical one.
This confirms the fix belongs in `export.py` as a correctness fix for
a real (if narrow, first-record) code path, not only as defensive
hardening against an impossible upstream state.

**Fix:** `build_spo2_binary` (`fiedle400/export.py`) now checks both
channels' validity together -- `s_byte`/`h_byte` are only written as
real values when *both* `spo2_valid and hr_valid`; otherwise both
bytes are written as the sentinel pair `(SPO2_INVALID_SPO2,
SPO2_INVALID_HR)`. A mixed sentinel pair can no longer be written
regardless of what the caller passes in.

**Test added:** `tests/test_export_spo2.py::
test_mixed_channel_validity_synchronizes_to_sentinel_pair` -- one
record with `spo2=98, heart_rate=None` and one with `spo2=0,
heart_rate=72` (out-of-range SpO2), asserting both payload bytes come
back as the sentinel pair in each case.

**Docs:** `SPO2_FORMAT.md` §5.2's OSCAR entry updated to mark the
discrepancy fixed, with the `device.py` reachability finding recorded
there too so it isn't lost.

**Tests:** `python3 -m unittest discover -s tests -t .` -- 290 run, OK
(skipped=7; was 289 before the new test). `pyflakes` is not installed
in this environment, so it was not run; no new imports were added, and
the change is a local branch restructure of existing variables.
