# T-072: Investigate `fiedle400 clear` against a Manual-mode recording

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`clear_memory`, `list_sessions`'s
    Manual-mode fallback, ~line 515-521)
  - `fiedle400/protocol/commands.py` (`build_delete_entry_command`)
  - `PROTOCOL.md` §3.13 (erase/delete commands, all reverse-engineered
    from Auto-mode captures) and §3.14 (Manual recording protocol)

---

## Description & Context

Noticed while reviewing `list_sessions()` after this cycle's Manual-mode
work (T-051, T-066): when the device is in Manual mode, the Auto-mode
session index (`0xEC`) returns nothing, so `list_sessions()` falls back
to querying the Manual-mode header (`0xA0`) and synthesizes a
`SessionInfo` with **placeholder** `session_id=1, user_id=1`
(`device.py` ~line 520) -- these are not real device-side identifiers
the way Auto-mode's `user`/`entry` fields are.

If someone runs `fiedle400 clear -s 1` while the device holds a
Manual-mode recording, `clear_memory()` sends the vendor's `9D 7F`
delete-entry sequence with that placeholder `user=1, entry=1` -- a
command format and byte layout reverse-engineered entirely from
**Auto-mode** captures (T-037/T-038/T-066). Whether the device (or the
real SpO2 Assistant) ever sends `9D 7F` to erase a Manual-mode recording
at all, and whether it would honor placeholder identifiers if so, is
unknown and untested. This session deliberately avoided erasing
anything while in Manual mode ("no erase" instruction, 2026-10-21) so it
was never exercised.

**Risk if wrong:** best case, the device ignores the command and
nothing happens (`clear` would then incorrectly report success). Worse
case, unknown -- not chased further without understanding the vendor's
actual behavior first.

## Criteria

- [ ] Capture the real SpO2 Assistant erasing a Manual-mode recording
      (if it's possible to do from that program at all), the way T-042
      captured Manual-mode download
- [ ] Determine whether `9D 7F` applies to Manual mode, and if so, what
      `user`/`entry` values (if any) actually matter
- [ ] If `fiedle400 clear` on a Manual-mode recording is currently wrong
      or a no-op, fix it or make it refuse clearly instead of silently
      claiming success
- [ ] `PROTOCOL.md` updated with the finding
- [ ] Tests pass

## Execution Notes

(Not started.)
