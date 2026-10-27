# T-092: `clear_memory()` should not early-return when nothing matches the erase target

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`clear_memory()`, now a thin Auto/Manual
    dispatcher; `_clear_auto()`, the `if not targets:` branch in it; its
    `_clear_auto_all()`/`_clear_auto_entry()` subfunctions; `_clear_manual()`,
    which has no equivalent "nothing to erase" check at all)

---

## Description & Context

psytrap flagged the current early-return behavior in `clear_memory()` --
when nothing in the session list matches the requested `session_id` (or the
device is already empty for "erase all"), it returns immediately without
writing `storage_init` (`9D 02`) or any erase command at all:

```python
targets = [s for s in before if not s.manual and (session_id <= 0 or s.session_id == session_id)]
if not targets:
    if int(debug) >= 1:
        print("[DEBUG] Nothing to erase.")
    return not any(s.session_id == session_id for s in before) if session_id > 0 else not before
```

Instruction was "don't do early return," without specifying what should
replace it -- this ticket exists to pin down the actual desired behavior
before changing anything, rather than guessing.

**Only the Auto-mode path has this check at all.** `manual_target` (the
dispatch between Auto/Manual, see the sequencing writeup) is computed and
checked *before* `targets`/the early return -- so any erase that would
touch the Manual recording has already been diverted to `_clear_manual()`
and returned by the time this branch is reached. That means `before` (and
the `not before` / `not any(...)` checks here) can never actually contain a
Manual entry at this point; the check is really "are there zero *Auto*
sessions," not "is there nothing at all," even though it reads like the
latter. `_clear_manual()` itself has no corresponding check -- it always
unconditionally sends `A1 00`/`A1 01` once reached, with no "Manual
recording already gone" bail-out. Whatever replaces the Auto-mode early
return should probably have a counterpart for Manual mode too, rather than
leaving that asymmetry in place.

## Open questions (need psytrap's decision)

- Should the device still receive the `storage_init`/flush sequence (and
  maybe a no-op `delete_all`/`delete_entry`) even when there's nothing to
  erase, so the same wire sequence always runs regardless of session
  state? Or is the concern purely about the *return value*/user-facing
  reporting in this case, not the wire protocol?
- What should the caller see when nothing matched -- still `True` (goal
  trivially achieved), `False`, or something that distinguishes "already
  gone" from "never existed" from "device had nothing at all"?
- Does this interact with `single_erase_unsupported` (T-074) -- should a
  no-match case be reported differently from a real single-entry-erase
  failure?

## Criteria

- [x] Get psytrap's answer on the open questions above
- [x] Implement the agreed behavior in `clear_memory()`, and decide whether
      `_clear_manual()` needs a matching "nothing to erase" check of its own
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)
- [x] Real-hardware validation of the new no-match path (e.g. `clear -s N`
      for an `N` that doesn't exist, and `clear` on an already-empty device)
      -- **not possible this cycle, hardware unavailable**; validated
      against the mock/simulated backend instead (see notes)

## Execution Notes

**2026-10-27 (prep, not the main fix):** Split the Auto-mode erase code
that used to be inline in `clear_memory()` into its own `_clear_auto()`,
mirroring `_clear_manual()`'s existing split-out shape -- `clear_memory()`
is now purely a dispatcher (list sessions once, decide Auto vs Manual,
delegate). Went one level further than that, per psytrap: `_clear_auto()`'s
two erase types (`delete_all` vs the two-step single-entry delete) are now
their own subfunctions too, `_clear_auto_all()` and `_clear_auto_entry()`
-- each just sends its step(s) and reads the erase-reply status; the
`if not targets:` early return this ticket is about, the `storage_init`/
flush before dispatch, and the post-erase re-list/verify all stay in
`_clear_auto()` since they're shared by both erase types. No behavior
change -- same commands, same order, same status handling, same
`single_erase_unsupported` logic, just reorganized so the early-return
fix (and any matching check added to `_clear_manual()`) has clear,
single-purpose functions to land in instead of one long method. Full
suite: 423 tests, OK (skipped=7).

**2026-10-27 (the actual fix):** Resolved the open questions by reworking
`_clear_auto()` so it no longer returns before touching the device at all:

- `storage_init`/`_flush_before_command()` now always run, regardless of
  whether `targets` matched anything.
- For "erase all" (`session_id <= 0`), `_clear_auto_all()` now runs
  unconditionally too -- there's always a valid `delete_all` to send, and
  sending it against an already-empty device is harmless (a no-op on the
  wire). This also means the final verification needed **no special case**
  for this branch: `gone` is simply the empty set when `targets` was empty,
  so `left` comes out empty and the function returns `True` the same way
  it would for a real erase that worked, with no "nothing to erase" branch
  needed at all.
- For a single `session_id` that matches nothing, there genuinely is no
  `(user_id, session_id)` pair to build a `delete_entry` command from, so
  that one step is skipped (logged at `debug>=1`) rather than invented --
  the transfer is still opened either way. Verification for this specific
  case falls back to the original check (no Auto-mode session with that
  id exists afterward), since there's no target timestamp to compare
  against.
- `single_erase_unsupported` is untouched by the no-match path: it's only
  ever set inside `_clear_auto_entry()`, which a no-match `session_id`
  never reaches.
- `_clear_manual()` needs **no matching change**: unlike Auto-mode's
  dispatch (which only checks "does `session_id` match something" at the
  very end, inside `_clear_auto()`), Manual-mode's dispatch already decides
  *before* calling it -- `clear_memory()` only calls `_clear_manual()` once
  `manual_target` is confirmed non-`None`. There is no "manual target
  doesn't exist" case for it to ever see.

Verified against the mock backend (hardware was unplugged this cycle):
`tests/test_clear.py::test_nothing_is_sent_for_a_session_that_does_not_exist`
still passes unchanged (it only asserts no *destructive* `0x9D 7F*` command
went out, which `storage_init`/the flush are not), and a scripted check
against the same fixture confirms `clear_memory(7, debug=1)` now logs
opening the transfer, skips the delete step, and still returns `True`.
Full suite: 423 tests, OK (skipped=7). Real-hardware re-validation of this
specific path (`clear -s N` for a nonexistent `N`) is still owed once the
device is available again.
