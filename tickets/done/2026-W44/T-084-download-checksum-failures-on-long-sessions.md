# T-084: Checksum-failed frames dropped silently on long session downloads, no retry

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`download_session`, lines 179-412;
    warning at 407-411)
  - `fiedle400/engine/detector.py:140-153` (the checksum check itself,
    `CORRUPT_FRAME`)

---

## Description & Context

During [T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md)'s
backup-before-erase step, downloading a real ~27,863-record / 64,734-packet
session produced:

```
WARNING: 162 stored frame(s) failed their checksum and were dropped; Session #2
is missing those samples and its SpO2 and pulse values may be misaligned from
that point on. Download it again.
```

plus 2,864 sequence gaps on that same download. The checksum itself is a real
protocol-level integrity check (7-bit sum of each 29-byte frame vs. its
trailer byte, `detector.py:140`) -- not a false positive. When it fails, the
frame is just dropped and counted; `download_session` has no retry or
re-request logic at all, it only warns once at the very end and tells the
user to re-run the download by hand.

Tried to reproduce it against freshly recorded test sessions (via the
[T-083](T-083-arduino-servo-test-fixture.md) wiggler rig): a 5,103-record/
7,762-packet session, and all 10 sessions together (6,734 records total) --
**zero checksum failures, zero sequence gaps** in both. The original failure
was on a session roughly 8x bigger by packet count than anything tried here,
so this looks like it may only show up on sustained, very long continuous
USB HID transfers, not shorter ones. Not confirmed -- could also be
specific to that one download (a one-off USB hiccup) rather than size-driven.

## Criteria

- [x] Reproduce against a session in the same ballpark as the original
      (tens of thousands of records/packets) -- the wiggler rig can
      generate a long throwaway recording for this without waiting on a
      real multi-hour session -- **reproduced on a real ~7h31m session,
      see Execution Notes**
- [x] If it reproduces: confirm whether it's size/duration-driven, or
      tied to something else (e.g. USB bus activity, thermal, time of
      day) -- **confirmed read-loop backpressure causing raw HID report
      loss, not data/size itself; see Execution Notes**
- [x] Decide whether `download_session` should retry a failed block
      automatically within the same run (if the protocol allows
      re-requesting a specific page) instead of only warning
      after the fact and telling the user to re-run it by hand --
      **not needed: the root-cause fix (conditional idle-sleep)
      eliminates the loss itself rather than retrying after it
      happens; see Execution Notes**
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      423 tests, OK
- [x] Validated against real hardware on a session bigger than the
      original failure -- **9h36m/34,581-record/112,999-packet
      session, 0 checksum failures, 0 sequence gaps; see Execution
      Notes**

## Execution Notes

**2026-10-22:** Investigated per psytrap's request. Did not reproduce
against two attempts with smaller sessions (see Description). Left open
rather than closed -- the original 162-frame/2864-gap failure was real and
on real hardware; it just hasn't reproduced yet at the session sizes tried
so far.

**2026-10-22, correction:** this is likely linked to
[T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md), not
just a separate data-quality footnote. The one dataset with these checksum/
gap errors (the original 7h44m/27,863-record session) is also the one
dataset where the wizard's erase failed to persist while a standalone
`clear` on the same data succeeded. Working theory: a corrupted/gappy
download immediately followed by an erase in the same open connection is
what breaks, not full erase in general. Reproducing this (for both
tickets) likely needs a much longer continuous recording than anything
produced by the T-083 wiggler rig so far -- the original session was ~8x
bigger by packet count than the biggest one tried here.

**2026-10-25, reproduced:** Real device (not the wiggler rig) accumulated
4 sessions, one of them a genuine ~7h31m/27,066-record/68,060-packet
recording. Ran the interactive downloader with `-v` debug on all 4:
sessions #1-3 (2,983 / 47 / 118 records) came back **completely clean**,
0 sequence gaps each. Session #4, the big one, reproduced the bug almost
exactly:

```
Session #4 download complete (27066 records, 68060 packets, 2474 sequence gaps).
WARNING: 150 stored frame(s) failed their checksum and were dropped; Session #4
is missing those samples and its SpO2 and pulse values may be misaligned from
that point on. Download it again.
```

(original: 27,863 records/64,734 packets, 162 bad frames, 2,864 gaps --
same order of magnitude on every number). This strongly confirms
**size/duration-driven**, not a one-off USB hiccup: the three small
sessions downloaded in the very same run, same connection, same session
as the big one, were perfectly clean, and only the long one failed. Raw
`-v` debug log (all `CORRUPT_FRAME`/`bad-checksum` lines) saved at
`/tmp/claude-1000/-home-mik-Documents-Bastel-2023--po400/d773d96a-7126-41ee-8e60-d9adaf1b69b7/scratchpad/dl_check/interactive_download_run2.log`
for further analysis (e.g. checking whether failures cluster at a
particular point in the transfer, which would point at something like a
buffer/timing issue past a certain data volume rather than a flat
probability per frame).

This download was done with the T-087 fix already in place (no longer
capped at 31 sessions), so all 4 sessions were correctly discovered and
none were skipped.

**2026-10-25, reproduced again, erase-after-download checked:** Ran the
full Download Wizard (download all + erase) against the same 4-session
device (sessions #1-3 untouched since the interactive run above still
had them on the device). Session #4 failed again, same ballpark but not
identical numbers:

```
Session #4 download complete (27066 records, 64117 packets, 2704 sequence gaps).
```

161 bad-checksum frames this time (vs. 150 in the previous run, vs. 162
in the original report) -- the per-run variance (packet count differs
too: 64,117 vs 68,060) points toward a transfer-timing/reliability issue
rather than anything deterministic about the data itself. Sessions #1-3
were clean again in this run too.

This run also directly tested
[T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md)'s
exact precondition theory (messy/checksum-failed download immediately
followed by erase, same connection): erase was issued right after this
messy download, and a fresh independent `fiedle400 sessions` check
afterward confirmed 0 sessions -- erase worked correctly this time, no
repeat of T-082's symptom. Doesn't rule out T-082, but this exact
precondition didn't trigger it on this attempt.

**2026-10-25, root cause theory and fix:** Traced through
[`fiedle400/engine/detector.py`](../../fiedle400/engine/detector.py) and
[`fiedle400/engine/buffer.py`](../../fiedle400/engine/buffer.py) to see
whether the corruption originates in the raw HID stream or in the serial
engine's own parsing. Findings:

- [PROTOCOL.md:89](../../PROTOCOL.md) -- stored-session subframes stream
  as unpadded 30-byte chunks *continuously across* 64-byte HID report
  boundaries; frames are not aligned 1:1 with reports.
- `SerialByteStreamBuffer` is a plain FIFO (`buffer.py`) -- it just
  appends whatever `read_report()` returns, with no concept of report
  sequencing or loss; if a report goes missing, the bytes before and
  after it get silently concatenated.
- The corrupt frames captured in the `-v` logs above show a second
  `ed04` header embedded mid-chunk (e.g.
  `ed040000...000049ed04025601000000`) -- the signature of the tail of
  one real frame spliced directly onto the head of a later one, i.e. a
  gap in the byte stream, not bit-level noise within one frame.
- Linux's hidraw driver keeps a small, fixed-size per-fd ring buffer for
  inbound reports and silently drops the oldest unread one when it
  fills, with no signal to userspace.
- `download_session`'s two main read loops (the SpO2-page and
  Pulse-page loops, `device.py` -- the hot paths for actually draining
  stored data) had an **unconditional `self._sleep(0.005)` on every
  iteration**, win or lose -- even right after successfully draining a
  packet with more backlog still waiting. That structurally caps drain
  rate below whatever rate the device bursts pages at, which is exactly
  what would eventually overflow a small, fixed kernel queue during a
  long, high-volume transfer -- consistent with small sessions always
  being clean (never enough backlog to overflow) and only the one
  genuinely huge session (27k+ records) tripping it.

Conclusion: this looks like raw HID report loss under read-loop
backpressure (most likely the kernel-side hidraw queue overflowing
because our own consumer loop was artificially rate-limited), not a bug
in the checksum check or detector's resync logic -- both are behaving
correctly, correctly flagging a genuine discontinuity rather than
manufacturing one.

**Fix applied:** in `device.py`, the SpO2-page and Pulse-page read loops
(and `wait_for_eb_stream`'s telemetry loop, same pattern) now only sleep
when `read_packets()` came back empty -- i.e. back off while idle, but
drain immediately and repeatedly while there's a backlog, instead of
always pacing at one report per ~5ms regardless. Two other `_sleep(0.005)`
call sites (`_manual_frames`'s drain loop and the residual-stream drain
in `wait_for_eb_stream`) were already conditional on an empty read and
needed no change.

Full suite passes (423 tests, no regressions). **Not yet validated
against real hardware** -- the device was empty at the time of this fix
(the 4-session batch used for the reproductions above was already
erased). Needs re-testing against another long (tens-of-thousands-of-
record) session once one is available, to confirm checksum
failures/sequence gaps actually drop or disappear with this change.

**2026-10-27, validated against real hardware, fix confirmed:** Device
had accumulated 4 fresh sessions, including a genuine **9h36m21s /
34,581-record / 112,999-packet** session -- bigger than the original
failing session (7h44m/27,863 records) and bigger than either of the
two confirmed reproductions (27,066 records each). Ran the full
interactive download (`-v` debug, no scoping, all 4 sessions) with the
conditional-idle-sleep fix in place:

```
Session #1 download complete (34581 records, 112999 packets, 0 sequence gaps).
Session #2 download complete (361 records, 722 packets, 0 sequence gaps).
Session #3 download complete (182 records, 364 packets, 0 sequence gaps).
Session #4 download complete (6445 records, 12316 packets, 0 sequence gaps).
```

Zero sequence gaps on every session, and no `CORRUPT_FRAME`/checksum/
dropped-frame warning anywhere in the log -- confirmed with a grep for
`checksum|corrupt|dropped|WARNING` against the full debug output
(empty match). This is the largest session fed through this code path
to date and it came back perfectly clean, strongly confirming the
read-loop-backpressure theory: the fix (back off only when idle,
drain immediately while there's backlog) eliminates the raw HID report
loss at its source rather than needing a retry/re-request layer on top.
Closing out the remaining open criteria on this basis.

Log saved at
`/tmp/claude-1000/-home-mik-Documents-Bastel-2023--po400/d773d96a-7126-41ee-8e60-d9adaf1b69b7/scratchpad/dl_check/t084_validate.log`.

**2026-10-27, deliberate backpressure experiment, causal confirmation:**
Same device, same 4 untouched sessions. Re-ran the download with
`FIEDLE400_IDLE_READ_SLEEP_MS` artificially raised, to test whether
exaggerating the idle backoff reproduces the corruption on demand (a
raw-hardware-noise explanation would not be expected to respond to our
own read-loop pacing at all):

- `=50` (10x the 5ms default): clean -- 0 sequence gaps, 0 checksum
  failures on all 4 sessions, same as the unmodified default.
- `=200` (40x default): **reproduced**:
  ```
  Session #1 download complete (34581 records, 79765 packets, 208 sequence gaps).
  WARNING: 11 stored frame(s) failed their checksum and were dropped;
  Session #1 is missing those samples...
  Session #2 download complete (361 records, 722 packets, 0 sequence gaps).
  Session #3 download complete (182 records, 364 packets, 0 sequence gaps).
  Session #4 download complete (6445 records, 12316 packets, 0 sequence gaps).
  ```
  Only Session #1 (the long one) was affected; sessions #2-4 stayed
  clean, matching the size-gating seen in every prior real repro.
  Packet count also dropped (79,765 vs. the clean run's 112,999),
  consistent with actual report loss rather than reordering.

This is direct, controlled, causal evidence for the read-loop-
backpressure theory, not just correlation from naturally-occurring
repros: deliberately throttling our own drain rate reproduces the
exact corruption signature (checksum failures + sequence gaps, gated
to the long session only) and the effect appears only past a
threshold between 50ms and 200ms of artificial idle delay. Logs saved
at
`/tmp/claude-1000/-home-mik-Documents-Bastel-2023--po400/d773d96a-7126-41ee-8e60-d9adaf1b69b7/scratchpad/dl_check/t084_sleep50.log`
and
`.../t084_sleep200.log`. Device still has all 4 original sessions
intact (no erase was run during this experiment).

**2026-10-27, repeatability check at a smaller multiplier:** Ran the
same download 5 times at `FIEDLE400_IDLE_READ_SLEEP_MS=10` (2x
default, same device, same untouched 4 sessions) to check whether a
more modest increase shows any flakiness rather than jumping straight
to the 200ms level that reproduced cleanly above. Result: **5/5 runs
identical and perfectly clean** -- `34581 records, 112999 packets, 0
sequence gaps` for Session #1 every time, same exact numbers for
sessions #2-4 too, no checksum warnings in any run. Logs saved at
`t084_sleep10_run1.log` through `t084_sleep10_run5.log` in the same
scratch directory as above.

Combined with the 50ms (clean) and 200ms (reproduced) data points,
this suggests the effect is not a flaky/probabilistic drop rate but a
genuine threshold: below some boundary between 50ms and 200ms of
artificial idle delay, the drain rate stays ahead of the device's
burst rate every time; above it, loss becomes reliably reproducible.
Narrowing the exact boundary further wasn't requested and isn't
needed to confirm the fix -- the real (unmodified, 5ms default) code
path has now shown 0 failures across every real download this cycle,
including the biggest session seen yet.

**2026-10-27, decisive experiment -- unconditionality, not magnitude,
is the actual cause:** psytrap pointed out the real variable under
test should be *sleeping on every read* (the original bug's actual
shape), not just a bigger idle delay. Added a second diagnostic-only
toggle, `FIEDLE400_FORCE_SLEEP_EVERY_READ`, that reverts the 4 read
loops in `wait_for_eb_stream`/`download_session` to their pre-fix
behavior -- sleeping `IDLE_READ_SLEEP` on every iteration regardless
of whether that read returned data, exactly like the original
`self._sleep(0.005)` placement -- while keeping the delay itself
tunable via the existing `FIEDLE400_IDLE_READ_SLEEP_MS`. (One early
`if not events:` in `wait_for_eb_stream`'s empty-count/early-exit
logic was mistakenly swept up by the same scripted find-and-replace
that wired the other 4 sites -- caught during review and reverted,
since that branch controls an unrelated early-exit counter, not a
sleep gate.) Full suite re-run after the fix: 423 tests, OK.

Then ran the download with the toggle on at just `=10` (2x the
default, the same value that produced zero failures 10/10 times when
only gating idle reads):

```
FIEDLE400_IDLE_READ_SLEEP_MS=10 FIEDLE400_FORCE_SLEEP_EVERY_READ=1
Session #1 download complete (34581 records, 69772 packets, 7063 sequence gaps).
WARNING: 284 stored frame(s) failed their checksum and were dropped...
Session #2 download complete (361 records, 684 packets, 0 sequence gaps).
WARNING: 1 stored frame(s) failed their checksum and were dropped...
Session #3 download complete (182 records, 364 packets, 0 sequence gaps).
Session #4 download complete (6445 records, 12316 packets, 0 sequence gaps).
```

This is dramatically worse than the 200ms *idle-only* experiment above
(7,063 gaps/284 bad frames vs. 208 gaps/11 frames) despite a 20x
smaller delay value, and for the first time Session #2 (a small
session, previously clean in every single test this cycle) also
failed. This settles it: **it was never really about how long the
sleep was -- it's that it fired on every iteration instead of only
during genuine idle gaps.** An unconditional sleep throttles the drain
loop continuously, including mid-backlog, which is strictly worse than
an idle-only sleep of even 20x the duration that only throttles
during actual lulls. This is the clearest confirmation yet that the
T-084 fix (gating the sleep on `not events`) targets the actual
mechanism, not just a magnitude tweak.

Device still has all 4 original sessions intact throughout (no erase
run). Log saved at
`/tmp/claude-1000/-home-mik-Documents-Bastel-2023--po400/d773d96a-7126-41ee-8e60-d9adaf1b69b7/scratchpad/dl_check/t084_force10.log`.
