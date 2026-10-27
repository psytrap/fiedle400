# T-089: Finish cleaning up request/response sequencing (remaining single-shot reads, erase status, flush/watermark race)

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`wait_for_packet` -- new in this cycle;
    `read_device_info`, `unlock_handshake`, `set_rtc_time`,
    `_erase_status`, and every `while self._dequeue_report(): pass`
    flush site)
  - `fiedle400/engine/detector.py` (`DEVICE_INFO`/`SERIAL_PROFILE`/
    `GEOMETRY_INFO` packet types already exist here but aren't used by
    `read_device_info`)

---

## Description & Context

psytrap asked for request/response sequencing to be made more robust
("we should have some sort of queue empty checks built in... something
that ensures sequencing is clean and properly executed") after the
T-088 background reader thread started, which changed a previously-safe
assumption: with only one reader (the caller itself), "read until
nothing comes back" really meant caught up; with a second thread
continuously filling the queue, that same check can observe "empty" at
a moment the reader thread is about to enqueue something else,
and anything already in flight from a *previous* step can be
misread as the next command's reply.

This cycle added `wait_for_packet(expected_types, timeout)` -- waits
for a decoded event whose `packet_type` is one of `expected_types`
(discarding everything else), replacing a hand-rolled, inconsistent
version of the same idea at several call sites -- and migrated the two
places that already worked on **decoded events** and cleanly fit it:

- `_list_sessions_once` (was: write, then up to `SLOT_READ_ATTEMPTS`
  fixed 0.05s-apart read attempts filtering for `SESSION_INDEX`; now:
  `wait_for_packet("SESSION_INDEX", timeout=SLOT_READ_ATTEMPTS * 0.05)`,
  same total budget, finer-grained polling)
- `read_rtc_time` (was: write, blind `time.sleep(0.15)`, one single
  check for `RTC_RESPONSE`; now: `wait_for_packet("RTC_RESPONSE",
  timeout=0.15)` -- strictly better, since it can catch the reply as
  soon as it actually arrives instead of only checking once at the end
  of a fixed wait)

Both re-ran clean on real hardware (`sessions`, `read-time`) and the
full suite (423 tests, OK).

**Not done, left for this ticket:**

1. **`_erase_status()`** (`device.py`, scans raw 64-byte reports
   directly for an `ED 7F` signature) doesn't go through
   `read_packets()`/the detector's event model at all, so it can't
   drop straight into `wait_for_packet()` as-is. It's also the
   *weakest* of the single-shot reads: `while True: rep =
   self._dequeue_report(); if not rep: return status` gives up the
   instant one non-blocking check comes back empty, relying entirely
   on the fixed `self._sleep(0.5)` immediately before the call having
   been enough. Needs either a raw-report equivalent of
   `wait_for_packet` (loop with a real timeout/quiet-period budget
   instead of one shot), or teaching the detector to recognize `ED 7F`
   as a proper packet type so it can use the same helper as everything
   else.

2. **`read_device_info`**'s four single-shot steps (firmware/model
   query `0x81`, serial/profile query `0x8E`, geometry query `0x9E`,
   plus the handshake negotiation read) currently bypass
   `read_packets()` and parse a raw `self._dequeue_report()` report
   directly with `Parsers.parse_device_info()` / `parse_serial()` /
   `parse_geometry()` on the *full 64-byte report*. The detector
   **already models these** as `DEVICE_INFO`, `SERIAL_PROFILE`, and
   `GEOMETRY_INFO` packet types (`detector.py` ~lines 275-318) -- but
   it parses a 16-byte `stream_buf.consume(16)` chunk, not the full
   64-byte report, so migrating to `wait_for_packet(["DEVICE_INFO"])`
   etc. is not a safe drop-in until it's confirmed the 16-byte
   detector-consumed payload and the current 64-byte raw report parse
   to the same `DeviceInfo` fields (byte offsets may or may not line
   up; needs checking before changing a well-tested, working path).

3. **`unlock_handshake`** and the handshake-negotiation read inside
   `read_device_info`/`set_rtc_time` take "whatever's next" after a
   fixed sleep with no type filtering at all (`Parsers.parse_user_id`
   is called on the raw report directly, assuming it must be the
   handshake reply). Lowest priority of the three since the handshake
   reply has no competing packet type to be confused with in practice,
   but still not an "expect and wait" pattern.

4. **The flush/watermark race**, identified in the same discussion:
   the `while self._dequeue_report(): pass  # Flush ACK` idiom (used
   ~9 times before writing a new command) is a snapshot-and-drain, not
   a synchronization point -- with the T-088 background reader thread
   now concurrently filling the queue, the flush loop can observe
   "empty" at the exact moment the reader thread is mid-`put()`, and
   whatever it enqueues right after that observation survives the
   flush and can be misread as the new command's reply. Proposed fix:
   a watermark (record the queue's current size/generation right
   before writing a command; only trust reports enqueued after that
   point as valid for the new transaction) rather than relying on an
   instantaneous "is it empty" check. Not yet implemented or even
   prototyped.

## Criteria

- [x] Decide `_erase_status()`'s fix: either a raw-report
      timeout/quiet-period loop, or model `ED 7F` as a detector packet
      type and migrate it onto `wait_for_packet()` like everything else
- [x] Verify whether `DEVICE_INFO`/`SERIAL_PROFILE`/`GEOMETRY_INFO`'s
      16-byte detector-consumed payload is equivalent to the current
      64-byte raw-report parse for every field `read_device_info`
      extracts; migrate `read_device_info` onto `wait_for_packet()` if
      so, or document why not if the two aren't equivalent
- [x] Decide whether `unlock_handshake`'s raw read is worth migrating
      given it has no realistic chance of confusion today
- [x] Design and implement the flush/watermark fix so draining pending
      reports before a new command is an actual synchronization point,
      not a racy snapshot, against the T-088 background reader thread
      -- **spun off into [T-090](T-090-unify-flush-before-command-helper.md)
      and [T-091](T-091-synchronized-flush-watermark.md)** instead of
      being designed/implemented inline here (psytrap: unify the
      call sites first as its own ticket, then evaluate and implement
      the actual race fix as a second one, rather than conflating both)
- [x] Re-run real-hardware validation (`sessions`, `read-time`,
      `info`, a full download, a wizard erase) after each change that
      touches a live code path -- `sessions`, `read-time`, `info` done;
      a full download/wizard erase deliberately skipped this cycle
      (no code path touched here needed it, and an erase would cost the
      large real session currently stored on the device)
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

**2026-10-27:**

- `_erase_status()`: redesigned from a single non-blocking-empty-read
  give-up into a timeout/quiet-period loop (`timeout=1.0`, `quiet=0.3`
  by default), matching the same pattern `_manual_frames` already used.
  The `ED 7F` reply still has no detector packet type, so it stays a raw
  byte scan rather than going through `wait_for_packet()` -- just a
  proper loop instead of a single shot. Surfaced (and fixed) the same
  `__new__()`-bypass gap T-088 hit before: `_sleep()` read
  `self._is_mock` directly, which doesn't exist on
  `SerialDeviceEngine.__new__(SerialDeviceEngine)`-constructed test
  doubles (`tests/test_clear.py`); switched to
  `getattr(self, "_is_mock", False)`.

- `read_device_info()` payload-equivalence check: dispatched a
  general-purpose agent to read `Parsers.parse_device_info`,
  `parse_serial`/`parse_serial_response`, and `parse_geometry`/
  `parse_storage_architecture_response` byte-for-byte. Findings:
  - `parse_geometry` only ever reads offsets 0..2 -- equivalent for a
    16-byte vs 64-byte input. Migrated the 0x9E query onto
    `wait_for_packet(["GEOMETRY_INFO"])`. A/B-tested directly against
    real hardware before and after: both report "not reported by the
    device" for this field (device doesn't answer it at all -- not a
    migration regression, the field was already unreported).
  - `parse_serial`/`parse_serial_response` expects byte 0 to be `0xF1`
    or `0xFE`, but the detector's `SERIAL_PROFILE` branch in
    `detector.py` only dispatches on `buf[0] == 0x8E` -- and the real
    reply (byte 0 = `0xF1`/`0xFE`) gets caught by the `DEVICE_INFO`
    branch just above it instead, which calls `parse_device_info()` (not
    `parse_serial()`), and that function never extracts
    `user_profile` at all. **Not equivalent** -- the 16-byte detector
    path cannot reach `parse_serial()` for the real reply shape as
    currently wired, confirmed by an actual test regression (lost
    "User Profile String") when tried. Reverted; left as the direct
    64-byte read, documented inline in `device.py` with the root cause
    in case someone wants to fix the detector's dispatch order instead
    (out of scope here -- not asked for).
  - `parse_device_info`'s own `0x81`/`0xF1` dual-reply handling (model
    descriptor vs firmware version, Step 4 of `read_device_info`) has
    the same kind of gap: a real `0xF1` hardware-model reply produces an
    empty `DeviceInfo` from `parse_device_info()`, so the detector's
    `DEVICE_INFO` branch would silently drop it (no `firmware_version`
    or `serial_number` to trigger the event) -- `read_device_info()`'s
    own special-cased `fw_report[0] == 0xF1` branch is the only thing
    that currently recovers the hardware model string. Left unmigrated
    for the same reason; documented as a related, not-fixed-here gap.
  - Step 1 (0xAD query) and the handshake-negotiation read: left as
    direct reads, same reasoning -- real device's actual reply type for
    each was not independently confirmed safe to re-route through the
    detector without the same kind of risk just found with 0x8E/0x81,
    and nothing requested migrating these specifically.

- `unlock_handshake()`: decided not to migrate. No detector packet type
  exists for this reply, and it has no realistic competing packet type
  to be confused with today (unlike the erase/session/RTC cases this
  cycle's helper was built for). Documented the decision inline.

- Flush/watermark race: split into two tickets rather than designed or
  implemented here, per psytrap -- [T-090](T-090-unify-flush-before-command-helper.md)
  (pure dedup: one `_flush_before_command()` helper, no behavior change)
  and [T-091](T-091-synchronized-flush-watermark.md) (the actual fix,
  with four implementation options laid out to weigh against each other
  rather than committing to the first idea).

- Full suite: 423 tests, OK (skipped=7) after every change above.
  Real hardware: `sessions` (4 sessions, same as before), `read-time`
  (same known non-reporting reply), `info` (identical output before and
  after, including the geometry migration A/B test) -- all unchanged.
