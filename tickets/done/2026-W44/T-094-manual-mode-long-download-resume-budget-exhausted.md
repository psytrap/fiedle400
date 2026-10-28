# T-094: Manual-mode download of a long recording loses almost all samples -- `_manual_series`'s fixed retry budget gives up too early

- **Status:** Done
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`_manual_series`, lines 726-757;
    `download_manual`, lines 759-794)

---

## Description & Context

10x wizard-driven, no-erase download of a real 11h38m52s / 41,932-record
Manual-mode recording (the long fixture-driven recording running
2026-10-27/28). Every single run printed:

```
Manual recording download complete (41932 records).
WARNING: the device sent N sample(s) fewer than its header announced;
those seconds are empty. Download it again.
```

`N` (samples missing) across the 10 runs: 41851, 41851, 41851, 41878,
41851, 41824, 41851, 41878, 41905, **41932** (run 10 got zero real
samples at all). That is **97-100% of the recording missing on every
run**, not an occasional dropped frame -- only the first ~27-108 seconds
of real data ever made it through before the download gave up and
silently padded the remaining ~11.6 hours with `probe-out`/`null`
placeholders.

The wizard and `download_manual()` still report this as success
(`✅ Successfully saved 41,932 records...`) with the full header-declared
record count -- the WARNING line is the only signal, and it's easy to
miss outside `-v`/`-vv`. Each of the 10 output HTML files looks complete
(same record count, same duration) but is actually ~97%+ empty.

**Root cause, found by reading `_manual_series` (`device.py:726-757`):**
A series (SpO2 or pulse) is downloaded 27 samples/subframe at a time.
When a subframe doesn't arrive within the 2.0s inner timeout, the code
asks again from the last-known-good subframe (`series_end` +
`series_request(opcode, expected)`) -- but only **3 times**
(`resumes >= 3: break`), then gives up on the *entire rest of the
series*, however many samples remain. For a long recording
(41,932 samples = ~1,553 subframes), 3 resume attempts is nowhere near
enough if the device needs to be nudged more than 3 times over the
course of over an hour of transfer -- and in every one of these 10 runs,
it needed far more than 3.

This is a different bug from
[T-084](../done/2026-W44/T-084-download-checksum-failures-on-long-sessions.md)
(Auto-mode `download_session`'s checksum-drop/no-retry issue, a
different code path) and from
[T-082](../done/2026-W44/T-082-wizard-erase-reports-success-but-sessions-persist.md)
(erase-after-download persistence) -- this is Manual mode's own download
path giving up on its own retry logic far too early, consistently, on
every run of this specific long recording. Nothing was erased during
this investigation (all 10 runs answered "no" to the wizard's erase
step), so the recording is still on the device for further testing.

## Criteria

- [x] Confirm whether raising/removing the fixed `resumes >= 3` cap (or
      switching to a smarter give-up condition -- e.g. only give up after
      N consecutive resumes make zero progress, not N resumes total) lets
      a full download of this same long recording complete with 0 (or
      near-0) missing samples. Needs real hardware -- the recording is
      still live on the device as of 2026-10-28.
- [x] Decide and implement the fix (resume budget, backoff, or both) --
      design call, not yet made.
- [x] `download_manual`'s success message should not call a download
      "Successfully saved" when the WARNING fired -- surface the
      missing-sample count as a visible failure/warning in the wizard
      output too, not only in `-v` debug logs.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

**2026-10-28 (Claude, at psytrap's request -- "do 10x download no-erase
with the wizard to check reliability" on the current long manual
recording):** 10/10 wizard runs (`python -m fiedle400.cli -v`, always
answering "no" to erase) completed without a crash and without ever
touching the erase path, but every run silently lost 97-100% of the
recording to this resume-budget cutoff. Confirmed by diffing the decoded
JSON across runs: all 10 runs agree record-for-record except for the
small `probe-out`/not-`probe-out` disagreement in the first ~80-160
samples where each run's download happened to give up at a slightly
different point (run 6 and 9 squeezed out ~80 more real seconds than
run 1 before hitting the cap; run 10 got none). Logs and the 10 output
HTML files are in the scratchpad under
`wizard_10x_manual/{run_1..10.log, files/wizard_manual_run_{01..10}.html}`
for reference if needed before a fix is validated.

**Correction:** the above claimed the WARNING line is "easy to miss
outside `-v`/`-vv`" -- checked again, that's wrong. Both the
"...download complete" line and the WARNING in `download_manual`
(`device.py:790-793`) are plain unconditional `print()`s, not gated by
`debug`. They were visible in every run regardless of `-v`. The real
visibility gap was narrower: the wizard's own success banner
unconditionally said "✅ Successfully saved ..." right after, with
nothing distinguishing a degraded download from a clean one at the
point that actually matters to a user skimming the output.

**2026-10-28, first fix attempt (budget -> consecutive-stall count):**
Changed `_manual_series`'s give-up condition from a fixed total of 3
resumes to `MAX_CONSECUTIVE_STALLS = 20` *consecutive* no-progress
resumes, reset on any progress (`device.py:727`). Added
`engine.download_warnings` (populated by `download_manual`) and changed
the wizard's success banner (`cli.py`, download-wizard branch) to print
a `⚠️` degraded-download message instead of `✅ Successfully saved` when
warnings were raised. Full suite passed (423 tests). psytrap flagged
that an initial attempt at the 10x full-length confirmation "seems
stuck" / "takes too long" -- correct observation: the process was alive
and reading the device (confirmed via `/proc/<pid>/stat` CPU-time
deltas and the HID fd being open), just legitimately slow now that it
was no longer bailing out after a few seconds.

**2026-10-28, real root cause found via live frame tracing:** Rather
than wait through a full-length run, wrote a quick direct-API script
(bypassing the wizard) requesting only a capped slice of the same real
session (150, then 2000 samples) with `_manual_frames` monkeypatched to
log every received frame's `(packet_type, subframe_seq)`. This revealed
the actual bug: `_manual_series`'s per-batch loop processed frames in
strict arrival order and executed `elif seq > expected: break` on the
*first* out-of-order frame -- discarding every frame after it in that
batch, including ones that matched `expected` and would otherwise have
been accepted. Real hardware delivers subframes with frequent small
gaps even outside any resume (e.g. `0,1,2,4,5,7,8,...` -- 3 and 6
simply never showed up in the first pass), and after a resume, the
freshly re-requested subframe routinely arrives interleaved with stale
frames still in flight from before the stop took effect, in no
guaranteed order. The first-fix attempt (above) only changed *when* a
resume fires; it didn't touch this `break`, so resumes were still being
wasted on data that had, in some cases, already arrived moments earlier
in the same batch.

Removed the `break`; every frame in a batch is now checked individually
against the current (possibly-advancing) `expected`. On the 2000-sample
capped test this alone went from "stuck for the full 20-stall budget,
WARNING fired, 123/150 samples missing" to "0 missing" -- but still slow
(39.2s for 2000 samples), because an out-of-order (ahead) frame was
still only *skipped*, not kept, so the gap it would have filled still
needed its own explicit resume round-trip later.

**2026-10-28, caching fix (psytrap: "for download we should have some
caching now. It's critical performance"):** Added a `pending: Dict[int,
List[int]]` cache in `_manual_series`, keyed by subframe number. An
out-of-order *ahead* frame is now decoded and cached instead of
discarded; whenever `expected` advances (naturally or via the cache
itself), the cache is drained for as many consecutive subframes as are
already available -- so a subframe received once is never silently
thrown away and re-requested from the device a second time, and this
also fixes an order-dependency the first fix still had (a frame later
in the same batch that *would* unlock an earlier one, had it been
scanned in a different order, is no longer missed). Real-hardware
result on the same 2000-sample capped request: **39.2s -> 2.7s**, 0
missing, down from dozens of stalls to 2 total resumes (one per
series). A 10,000-sample capped run: 18.1s, 0 missing, 4 resumes total
-- extrapolated full-length (41,932 samples) around ~75s, down from an
earlier ~14 min/run estimate before this fix.

**2026-10-28, final full-length 10x confirmation (real hardware, same
untouched 41,932-record/11h38m52s recording throughout):** All 10
wizard runs (download -> answer "no" to erase) completed cleanly: every
run saved all 41,932 records, 0 missing samples, erase correctly
declined/"Flash recordings preserved" every time. Diffed the decoded
JSON across all 10 output HTML files: **byte-for-byte identical across
every run, 0 diffs**, including a consistent 81 genuine `probe-out`
samples at the very start of the recording (finger not yet placed --
real data, not loss). This is a stronger result than the original
clean-looking (but ultimately misleading) earlier validations in
[T-082](../done/2026-W44/T-082-wizard-erase-reports-success-but-sessions-persist.md)/[T-090](../done/2026-W44/T-090-unify-flush-before-command-helper.md),
which only ever exercised short test sessions and never actually hit
this code path's failure mode. Device confirmed still holding the
original session afterward (`fiedle400 sessions`), untouched.

**2026-10-28, root cause of the remaining resumes (psytrap: "investigate
the root cause for the resumes in the 10000 recording. Too strict
timeouts?"):** Not a timeout issue. Verified by requesting the SpO2
series directly and passively listening for a continuous 15s window
with no resume/stop-restart logic active at all, logging every
subframe seen. The device streamed 1,435 subframes naturally in that
window but **permanently skipped roughly 1 in 4 of them** in a
repeating pattern (3, 6, 9, 12, 19, 22, 25, 28, 35, ...) -- none of
those ever appeared, even 15s and 1,400+ subframes later. So the gaps
are not us reading too slowly or `_manual_frames`'s 2.0s/0.3s
timeout/quiet window cutting off too early -- the device's manual-mode
series stream deterministically never (re)sends certain subframes on
its own; the explicit stop + re-request is the actual mechanism the
protocol requires to backfill them (matching this method's existing
docstring note that SpO2 Assistant does the same `9N 7F` / `9N 00`
dance). The caching fix above doesn't eliminate the need for these
resumes -- it makes each one cheap and correct (fetches exactly the one
gap that's missing) instead of wasteful (re-fetching data already
received and discarded) or destructive (the old `break` bug).
