# T-088: Evaluate a continuously-running background reader thread for the serial engine

- **Status:** Done
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`SerialDeviceEngine`, all methods that
    call `self.dev.read_report()` or `self.read_packets()` directly --
    `wait_for_eb_stream`, `download_session`, `list_sessions`/
    `_list_sessions_once`, `clear_memory`, `_manual_frames`, and others)
  - `fiedle400/hid_driver.py` (`PulsoxHidRawDevice.read_report`,
    `PulsoxHidLibDevice`)
  - `fiedle400/engine/buffer.py` (`SerialByteStreamBuffer` -- would need
    thread-safety if a background thread writes to it)
  - `tests/hwsim.py` (mock devices assume synchronous request/response;
    would need rework to support a continuously-polling consumer)

---

## Description & Context

[T-084](done/2026-W44/T-084-download-checksum-failures-on-long-sessions.md)
root-caused checksum/sequence-gap corruption on long downloads to an
unconditional per-iteration sleep in the main read loops, which capped
drain rate below the device's burst rate and risked overflowing the
kernel's small, fixed hidraw inbound report queue (silent drop on
overflow, no signal to userspace). The fix made the sleep conditional
on an empty read, validated clean on real hardware up to a 9h36m/
34,581-record/112,999-packet session (the biggest tried so far) --
see T-084's Execution Notes, including a deliberate experiment
(`FIEDLE400_FORCE_SLEEP_EVERY_READ`, since removed) that confirmed it
was specifically the *unconditional* sleep, not sleep duration, that
caused the loss.

That fix minimizes the gap between reads during an expected-data
window, but it's still a synchronous design: all reading happens
inline in whichever method is actively waiting for a reply, bounded by
that method's own timeout/retry logic. Between high-level operations
(e.g. the moment between a download finishing and `clear_memory`
starting), nothing is draining the fd at all except each method's own
one-time flush loop (`while self.dev.read_report(64): pass`) run right
before it writes its own command.

psytrap raised the idea of a **continuously-running background reader
thread** instead: one dedicated thread whose only job is to drain
`read_report()` into a thread-safe queue/buffer as fast as the OS
yields reports, decoupled entirely from whatever the main thread is
doing (writing commands, parsing, sleeping, or sitting idle). This
would not just minimize the backpressure window like the T-084 fix
does -- it would remove read-loop pacing as a possible cause of report
loss altogether, since the consumer never pauses regardless of what
the rest of the engine is up to.

It was also raised as a possible (but speculative, unconfirmed)
explanation for [T-082](done/2026-W43/T-082-wizard-erase-reports-success-but-sessions-persist.md)
(wizard erase reporting success but not persisting) -- the theory being
that stray/delayed bytes from the tail of a download could still be
in flight when the post-erase re-list runs immediately after. This is
weak so far: every method already flushes pending reads before issuing
its own command, and the exact "messy download immediately followed by
erase" precondition was reproduced and retested twice in T-084/T-082's
Execution Notes without ever reproducing T-082's actual bug. No
concrete mechanism has been identified connecting read timing to T-082;
it's one open hypothesis among others (e.g. flash-commit timing, which
[T-085](done/2026-W44/T-085-clear-poll-timeout-retry.md)'s settle delay
already targets).

## Criteria

- [x] Decide whether this is worth building at all, given the T-084 fix
      already validated clean on the largest real session tried so far --
      **built anyway, per psytrap's explicit instruction ("draining the
      HID interface is clean therefor implement t88 now")**
- [x] If pursued: design how a single background reader thread would
      integrate with the existing synchronous method structure -- **opt-in
      `background_reader=True` constructor flag; a thread-safe
      `queue.Queue` fed by one dedicated thread; every internal read
      routed through a new `_dequeue_report()` instead of calling
      `self.dev.read_report()` directly; lifecycle via `engine.close()`
      (stops the thread, then closes the device); see Execution Notes**
- [x] If pursued: decide how `tests/hwsim.py`'s mock devices support this
      without breaking their synchronous, scripted-response test model --
      **they don't: a module-level `SIMULATED_DEVICE_ACTIVE` flag forces
      the background reader off for every test fixture, real or
      mock-backed; see Execution Notes for why a naive approach broke
      six tests first**
- [x] If pursued: re-run the T-084 real-hardware validation (or
      equivalent) against the new design to confirm it's at least as
      reliable as the current fix, not a regression -- **re-ran the same
      9h36m/34,581-record/112,999-packet download with the background
      reader actually active: 0 sequence gaps, 0 checksum failures,
      identical packet counts to every prior clean run**
- [x] Explicitly record whether this ends up explaining or ruling out
      T-082 -- **not exercised by this ticket at all; T-082 remains open
      and unconfirmed, no claim is made here either way**
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      423 tests, OK (same count and runtime as before this ticket)

## Execution Notes

**2026-10-27, implemented (Claude, at psytrap's explicit instruction):**
Added an opt-in background reader thread to `SerialDeviceEngine`
(`fiedle400/engine/device.py`):

- `__init__(self, device, background_reader: bool = False)` -- off by
  default, so every existing caller (all of `tests/`, and every CLI
  construction site before this change) behaves exactly as before
  unless it explicitly opts in.
- When enabled, `_start_reader_thread()` spins up one daemon thread
  (`_reader_loop`) whose only job is `self.dev.read_report(64)` in a
  tight loop, pushing whatever comes back into a `queue.Queue`
  (sleeping 1ms only when a read comes back empty, to avoid
  busy-spinning a CPU core for nothing).
- A new `_dequeue_report(timeout=0.0)` is now the **only** way anything
  else in the class reads a report: with the thread active it pulls
  from the queue (blocking up to `timeout`); otherwise it calls
  `self.dev.read_report(64)` directly, byte-for-byte what every call
  site did before this ticket. All 19 previous direct
  `self.dev.read_report(64)` call sites (`read_packets`,
  `wait_for_eb_stream`, `download_session`, `read_device_info`,
  `list_sessions`/`_list_sessions_once`, `_manual_frames`,
  `read_manual_header`, `download_manual`, `clear_memory`,
  `_manual_delete_step`, `_erase_status`, `set_rtc_time`,
  `unlock_handshake`) were routed through `_dequeue_report()` with a
  scripted replace, careful to exclude the two call sites that must
  stay direct (the reader thread's own read, and `_dequeue_report`'s
  own non-threaded fallback).
- `engine.close()` is new: stops the reader thread (if running), then
  closes the device -- the single place anything using the background
  reader needs to clean up.
- `fiedle400/cli.py`: all 9 real command handlers
  (`detect`/`download`/`sessions`/`clear`/`read-time`/`set-time`/
  `selftest`/`info`/the interactive wizard) now construct
  `SerialDeviceEngine(dev, background_reader=True)` and call
  `engine.close()` instead of `dev.close()` in their `finally` blocks.
  The interactive wizard's one place that read a raw report directly
  off `dev` (the post-handshake probe, bypassing the engine) was
  switched to `engine.read_raw_report()` -- with the thread running,
  anything else touching `dev.read_report()` directly would race it,
  since the fd only has one legitimate reader once the thread starts.

**Test-fixture fallout, found and fixed the same session:** psytrap
flagged "this can have a major test impact" and "you need proper test
fixtures" before this was validated against the suite, which caught a
real problem: `tests/hwsim.py`'s `HidrawSim` and
`tests/test_hwsim_hidbackend.py`'s fake `hid` module both simulate a
device by patching OS-level calls (`os.open`/`os.read`/`os.write`, or
`sys.modules["hid"]`) underneath the *real* `PulsoxHidDevice` class --
they have no `.responses` attribute, so the existing `_is_mock`
duck-typing check does not exclude them, and several tests drive real
`cli.main()` end-to-end against these fakes. A first attempt gated the
background reader with an env var (`FIEDLE400_NO_BACKGROUND_READER`)
set by the fixtures; this broke differently than expected because
`run_cli()`'s own `scrub_env()` call -- used throughout the suite to
give `cli.main()` a clean environment -- strips every
`FIEDLE400_`-prefixed var, wiping the signal out again right before
`cli.main()` ran. Switched to a plain module-level flag instead
(`SIMULATED_DEVICE_ACTIVE` in `device.py`, patched via
`mock.patch.object` in both fixtures' setup/`__enter__`), which
`scrub_env()` has no effect on. With that in place: **423 tests pass,
same count and ~10s runtime as before this ticket** -- confirming no
background thread starts in any test, mock-backed or
simulated-hardware-backed alike.

One more fixture gap, unrelated to this ticket: `tests/test_clear.py`'s
`test_the_vendor_captures_erase_reply_reads_as_done` constructs a
`SerialDeviceEngine` via `__new__` (bypassing `__init__` entirely) to
test `_erase_status()` in isolation -- `_dequeue_report()` was made
tolerant of that (`getattr(self, "_use_background_reader", False)`)
since none of the new attributes exist on such an instance.

**Real-hardware validation:** with all 4 sessions still on the device
from T-084's validation (including the 9h36m/34,581-record one), ran:
`sessions` (all 4 sessions listed correctly), the full interactive
wizard up to session listing (handshake, device info, session listing
all correct, clean quit via `engine.close()`), and the full `download`
of all 4 sessions with the background reader thread actually active:

```
Session #1 download complete (34581 records, 112999 packets, 0 sequence gaps).
Session #2 download complete (361 records, 722 packets, 0 sequence gaps).
Session #3 download complete (182 records, 364 packets, 0 sequence gaps).
Session #4 download complete (6445 records, 12316 packets, 0 sequence gaps).
```

Identical to every prior clean run of this exact session. Also
confirmed the process exits promptly afterward (`time fiedle400
sessions` -- 0.5s), i.e. the daemon reader thread does not hang the
process on exit. Log saved at
`/tmp/claude-1000/-home-mik-Documents-Bastel-2023--po400/d773d96a-7126-41ee-8e60-d9adaf1b69b7/scratchpad/dl_check/t088_bgreader.log`.

Not done: T-082 was not re-tested against this change (no erase was
run this session to preserve the device's data for comparison across
T-084/T-088's validations) -- this ticket makes no claim about T-082
either way, per its own criterion above.
