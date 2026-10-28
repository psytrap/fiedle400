# T-085: `clear_memory` should poll with a timeout/retry, not a single immediate re-list

- **Status:** Open (deferred)
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`SerialDeviceEngine.clear_memory`, lines 728-784)

---

## Description & Context

[T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md)'s
leading theory is that `clear_memory`'s success check is a single
immediate re-list (`after = self.list_sessions(...)`, right after a
fixed `self._sleep(0.5)` following the delete command) -- and that this
re-list can reflect a transient/not-yet-committed device state rather
than what's actually durable in flash. The one real repro so far
(wizard erase after a messy, checksum/sequence-gap-heavy download)
reported success but the session was still there afterward; three
later attempts on clean downloads could not reproduce it, which is
consistent with the device sometimes needing more than 0.5s (or more
than one listing attempt) to settle, especially coming off a rough
download.

Today's run of the full wizard flow (download all 4 sessions, including
a 1h58m/7,124-record one, then erase) worked fine on the first
try -- so this is not "always wrong," it's "sometimes not durable yet,"
which is exactly the kind of flake a single immediate check can't tell
apart from a real failure.

Right now, if the post-erase `list_sessions()` call still shows the
target, `clear_memory` just returns `False` once -- no retry, no
back-off, nothing. The wizard and `clear` CLI command take that `False`
at face value.

## Criteria

- [x] ~~`clear_memory` polls `list_sessions()` up to some bounded
      timeout/retry count (with a short delay between attempts)
      instead of checking exactly once, before deciding the erase
      didn't take~~ -- **psytrap chose a simpler alternative instead of
      a poll/retry loop: see Execution Notes**
- [x] The timeout/retry parameters are reasonable defaults, not
      something that makes every normal erase noticeably slower than
      today's quick 0.5s+one-check path -- **n/a under the simpler
      approach taken; see notes**
- [ ] ~~`-vv` logs each poll attempt~~ -- n/a, there is no poll loop now
- [x] If it still fails after exhausting retries, behavior is
      unchanged from today (reports failure -- doesn't silently claim
      success) -- still a single pass/fail check, just after a longer
      settle delay
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      423 tests, OK
- [x] Noted back on T-082 once this lands, since it may turn out to
      explain (or rule out) that ticket's intermittent repro

## Execution Notes

**2026-10-22 (Claude, at psytrap's request):** psytrap separately
flagged that `list_sessions()` is known to come back empty
sporadically -- a different symptom than this ticket's (this ticket is
about a post-erase re-list still showing the *target*; that one is
about a plain listing coming back with *nothing at all* when sessions
do exist). Fixed that one directly: `list_sessions()` now retries its
underlying query up to 3 times (0.3s apart) before trusting an empty
result, logged at `-vv` (`fiedle400/engine/device.py`,
`list_sessions`/`_list_sessions_once`). A genuinely empty device still
correctly reports empty after all 3 attempts, so this only guards
against false negatives.

Since `clear_memory`'s `before`/`after` checks both call
`list_sessions()`, they get this same empty-result retry for free now
-- but this ticket's actual criteria (retry when the post-erase list
still shows the erased target, i.e. a false *positive* for "still
there") is a different code path (the `left = [...]` check after
`after = self.list_sessions(...)`) and is still open/unaddressed.

**2026-10-25, resolved with a simpler fix instead of poll/retry:**
After investigating why the one real T-082 occurrence might have
happened, psytrap explicitly asked for a different, simpler approach
than this ticket originally called for: instead of a bounded poll/retry
loop around the post-erase re-list, just increase the settle delay
before that one check, and keep reporting a single pass/fail -- no
retry logic at all.

Implemented in [`fiedle400/engine/device.py`](../../fiedle400/engine/device.py):
added `ERASE_SETTLE_SECONDS = 3.0` (up from the prior implicit 0.5s used
only for the erase-command-accepted check) and a new
`self._sleep(ERASE_SETTLE_SECONDS)` right before `after =
self.list_sessions(debug=debug)` in `clear_memory`. Rationale: the `ED
7F` erase reply only confirms the device *accepted* the command, not
that the flash write has physically committed yet (see the T-082
write-up); giving it several seconds before trusting the re-list
addresses the same suspected race as a poll loop would, with much less
code and no new failure modes of its own (a poll loop adds its own
timeout tuning and logging surface this avoids entirely).

Full suite passes (423 tests, no regressions -- `_sleep` is a no-op for
mocked test devices, so none of the existing tests got slower). Not yet
re-verified against a real device erase (none connected at the time of
this change); next real erase run should confirm this doesn't introduce
a noticeably slower `clear`/wizard-erase experience and, ideally, that
if T-082 ever recurs, it's visibly fixed by the longer settle time.
