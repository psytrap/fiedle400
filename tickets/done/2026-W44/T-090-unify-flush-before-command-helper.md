# T-090: Unify the "flush stale reports" idiom into `_flush_before_command()`

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` -- every `while self._dequeue_report(): pass`
    site (`download_session` x2, `_list_sessions_once` x2, `download_manual`,
    `set_rtc_time`, `clear_memory`, `read_manual_header`, `_manual_delete_step`)

---

## Description & Context

T-089 flagged that the repeated `while self._dequeue_report(): pass  # Flush
ACK`/`# Flush stale reports` idiom (roughly 9 call sites in `device.py`) is
hand-rolled at every site rather than going through one shared helper. This
ticket is the **mechanical half only**: extract a `_flush_before_command()`
method, call it everywhere the idiom currently appears, with no behavior
change and no attempt to fix the race condition that idiom has against the
T-088 background reader thread (that's a separate, harder problem -- see
[T-091](T-091-synchronized-flush-watermark.md)).

Rationale for splitting it this way (psytrap, 2026-10-27): unifying the
repeated code is worth doing on its own even before the race is solved, and
conflating "dedupe this" with "make this actually correct" risks a ticket
that never lands either goal cleanly.

## Criteria

- [x] One `_flush_before_command()` method (or similarly named) replaces every
      `while self._dequeue_report(): pass` site listed above, byte-for-byte
      equivalent behavior (still just drains whatever is already queued,
      nothing more)
- [x] No call site's timing/retry budget changes
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)
- [x] Real-hardware smoke check on at least one path that uses it
      (`sessions`, `read-time`, a small download)

## Execution Notes

**2026-10-27:** Added `_flush_before_command()` right next to
`_dequeue_report()`/`read_raw_report()` in `device.py`; its body is the exact
same `while self._dequeue_report(): pass` loop, just named and in one place.
Replaced all 9 sites with a call to it (2 in `download_session`, 2 in
`_list_sessions_once`, 1 each in `download_manual`, `set_rtc_time`,
`clear_memory`, `read_manual_header`, `_manual_delete_step`), preserving any
trailing `# Flush ACK` comment. No timing, retry counts, or control flow
touched -- purely the mechanical dedup this ticket scoped, explicitly not
the T-091 race fix.

Full suite: 423 tests, OK (skipped=7). Real hardware: `sessions` (same 4
sessions) and `read-time` (same reply) unchanged; also ran a real small
download (`download -s 3 -t 5`, which exercises `download_session`'s two
flush sites) -- 5/5 records, 262 packets, 0 sequence gaps, output identical
in shape to prior downloads.

**Follow-up (same day):** gave `_flush_before_command()` a `debug` parameter
(threaded through from all 9 call sites, which already had `debug` in
scope) that counts drained reports and, at `-v`/`debug>=1`, prints
`[DEBUG] _flush_before_command() dropped N stale report(s)` -- matching the
existing `[DEBUG]`/`[DEBUG IN]`/`[DEBUG OUT]` logging convention elsewhere
in `device.py`. Silent when nothing was drained, so normal `-v` runs aren't
spammed with a zero-count line every call. Verified on real hardware
(`sessions -v`): showed `dropped 1 stale report(s)` ahead of the
`SESSION_INDEX` debug lines. Full suite re-run: still 423 tests, OK
(skipped=7).
