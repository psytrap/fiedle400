# T-074: `fiedle400 clear -s N` (single Auto-mode session) does not erase anything on real hardware

- **Status:** Open (psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`clear_memory`, the `session_id > 0` branch)
  - `fiedle400/protocol/commands.py` (`delete_entry`)
  - `PROTOCOL.md` §3.13 ("Delete (the selected recordings)" row)
  - `fiedle400/cli.py` (`_report_erase` -- the misleading message this
    uncovered, already fixed)

---

## Description & Context

While re-confirming Auto-mode erase still works after T-072/T-073's
Manual-mode erase work, tried `fiedle400 -v clear -s 1 -y` against a
real device with two real Auto-mode sessions on it. Result:

```
[DEBUG OUT] Delete user 1 entry 1, series 2 (0x9D 0x7F 0x02): 9d7f0201010000200000000000000000
[DEBUG] Erase reply status: none
[DEBUG OUT] Delete user 1 entry 1, series 1 (0x9D 0x7F 0x01): 9d7f01010100001f0000000000000000
[DEBUG] Erase reply status: none
⚠️ Session #1 still listed on the device after the erase.
```

A follow-up diagnostic script sent the same two commands and polled for
up to 5s: the device answered each with a plain `F0 70` ack, never an
`ED 7F` erase-reply, and the session was byte-identical before and
after. **The single-entry `9D 7F 02/01 [user][entry]` delete does not
erase anything on this real device.**

By contrast, `fiedle400 clear -y` (delete all, `9D 7F 7F 7F 7F`) was
tried right after and worked correctly: `ED 7F ... 00` (status 0), and
both sessions were actually gone afterwards (`sessions` reported "No
stored recording sessions found").

Checking `PROTOCOL.md` §3.13: the single-entry delete byte layout was
always static analysis only (T-037, decoded from `SpO2.exe` at
`0x4af43c`) -- unlike Delete All, no vendor capture was ever found that
actually sends it. This real-hardware result is the first time it was
tried against real hardware, and it fails the same way the Manual-mode
`A1` sequence would have if that one had turned out to be wrong: `clear`
noticed (its existing re-list verification caught this correctly,
exit 1, no false success) but the single-entry byte layout itself does
not work.

**Also found and already fixed in passing:** `_report_erase()`'s failure
message hardcoded "A Manual-mode recording is not erased this way",
which is wrong when the actual failure is an Auto-mode single-session
delete (as it was here). Changed to a generic message that does not
guess at a cause (`fiedle400/cli.py`).

## Criteria

- [ ] Determine the real single-entry delete byte layout (another static
      analysis pass on `SpO2.exe`, or a packet capture of the Delete
      button against a single Auto-mode recording -- same approach as
      T-072/T-073 used for Manual mode)
- [ ] Fix `clear -s N` to actually erase on real hardware, or make it
      explicitly fall back to (and say it is falling back to) delete-all
      when erasing a single session is not currently possible
- [ ] `PROTOCOL.md` §3.13 updated with the real byte layout once known
- [ ] Tests pass

## Execution Notes

**Found and diagnosed (local, 2026-10-21).** See Description above for
the full real-device evidence: per-entry delete gets a bare `F0 70` ack
and changes nothing; delete-all gets `ED 7F ... 00` and actually empties
the device. Not yet fixed -- `clear -s N` currently honestly reports
failure (via the existing re-list check) rather than lying about success,
so nothing is silently broken for users, but a single session cannot
currently be erased without also erasing every other recording.
