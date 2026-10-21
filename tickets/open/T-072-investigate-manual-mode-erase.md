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
- [x] Determine whether `9D 7F` applies to Manual mode, and if so, what
      `user`/`entry` values (if any) actually matter (static analysis: it
      does not; the vendor uses `A1`, see Execution Notes)
- [ ] If `fiedle400 clear` on a Manual-mode recording is currently wrong
      or a no-op, fix it or make it refuse clearly instead of silently
      claiming success
- [x] `PROTOCOL.md` updated with the finding (static analysis, §3.14 G)
- [ ] Tests pass

## Execution Notes

**Static analysis of `SpO2.exe` (cloud, 2026-10-21, patch 0033; ticket stays deferred).**
- The vendor does not use `9D 7F` for Manual recordings. It has its own erase, `A1 00 21`. After
  the device's `D1 00 [status]` reply it sends `A1 01 22`, then `A1 04 25` when the third-series
  flag is set. Each step waits for status 0. Full write-up and addresses: PROTOCOL.md §3.14 G and
  the §3.13 table.
- Sent by the Delete button and Delete User when the device did not report the Auto-mode
  categories, and after a Manual download when a stored setting is on (the Manual
  counterpart of the Auto-mode automatic delete).
- The one Manual capture has no `A1`, so it shows no erase. Nothing here has been seen on the
  wire.
- Correction to the description above: `clear_memory()` filters out Manual sessions
  (`not s.manual`), so `clear -s 1` on a Manual recording sends no `9D 7F` at all. It reports
  that the recording is still listed and exits 1, rather than claiming success.
- Still open: whether the device erases on `A1 00` (capture SpO2 Assistant's Delete on a Manual
  recording), and whether `fiedle400 clear` should send it.
