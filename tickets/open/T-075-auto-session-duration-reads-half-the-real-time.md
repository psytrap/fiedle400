# T-075: Auto-mode session duration/record count reads ~half the real recording time

- **Status:** Open (psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`list_sessions`, the `0xEC` ->
    `SessionInfo` mapping: `record_count`, `duration_sec`, `raw_samples`)
  - `fiedle400/protocol/parsers.py` (or wherever the `0xEC` session-index
    payload is decoded -- `raw_samples`/record-count fields)
  - `PROTOCOL.md` §3.2 (`0xEC` session index table)

---

## Description & Context

While testing T-074 (Auto-mode erase), psytrap made two real recordings
on the device, each timed at 60 seconds. `fiedle400 sessions` listed
both as 30 records / 30s:

```
Session ID   | User   | Records    | Duration     | Timestamp
1            | 1      | 30         | 30s          | 2026-10-21 17:31:35
2            | 1      | 30         | 30s          | 2026-10-21 17:32:50
```

The diagnostic script run for T-074 printed the underlying
`SessionInfo` and showed `record_count=30, duration_sec=30,
raw_samples=59` for a recording psytrap says actually ran 60s. 59 raw
(2 Hz) samples is ~29.5s, consistent with the *reported* 30s -- so
whatever produces `raw_samples=59` (and hence `record_count`/
`duration_sec`) is the thing that's off by about half, not a display
rounding issue downstream of a correct raw value.

Also worth checking: the gap between the two session timestamps
(`17:31:35` -> `17:32:50`) is 75s, versus the ~10s gap psytrap actually
left between recordings -- consistent with the first recording's real
duration being roughly double what was reported (60s real + ~10s gap +
60s real landing closer to +130s if both are halved to 30s each, the
math doesn't trivially reconcile, so this needs an actual re-check
against the real timestamps rather than guessing from memory).

**Not yet investigated:** whether this is a decode bug (e.g. reading a
7-bit field as fewer bits, or reading the wrong byte offset), a real
device sampling-rate quirk, or something about how these two specific
test recordings were started/stopped. No code changes have been made.

## Criteria

- [ ] Reproduce with a fresh, precisely-timed recording (e.g. exactly
      60s by a stopwatch) and compare the device's own on-screen
      duration (if it shows one) against what `fiedle400 sessions`
      reports
- [ ] Determine whether the `0xEC` raw-sample count itself is wrong, or
      whether `record_count`/`duration_sec` are computed wrong from a
      correct raw value (`PROTOCOL.md` §3.2's 2 Hz raw-sample assumption)
- [ ] Fix the decode/computation if it's a real bug, or document why the
      reported duration is correct and the discrepancy was a timing
      mistake on the human side
- [ ] `PROTOCOL.md` updated if the finding changes what §3.2 claims
- [ ] Tests pass

## Execution Notes

(Not started.)
