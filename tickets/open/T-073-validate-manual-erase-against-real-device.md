# T-073: Validate `fiedle400 clear`'s Manual-mode `A1`/`D1` erase against real hardware

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`_clear_manual`, `_manual_delete_step`)
  - `fiedle400/protocol/manual.py` (`delete_step`, `parse_delete_reply`)
  - `PROTOCOL.md` §3.14 G (static analysis, unconfirmed)
  - `tickets/open/T-072-investigate-manual-mode-erase.md` (the
    investigation this follows on from)

---

## Description & Context

T-072 implemented `fiedle400 clear` against a Manual-mode recording:
it now sends `A1 00`, then `A1 01` once the device confirms the first,
following SpO2.exe's own command layout from static binary analysis
(patch 0033). This has never been seen on the wire -- not in the one
Manual-mode capture on hand, and not tried against a real device,
since the one real-hardware attempt this cycle was deliberately not
followed through to an actual erase.

The implementation verifies its own result by re-listing afterwards
(same pattern as the Auto-mode `9D 7F` path), so a wrong byte layout
should surface as "still listed" rather than a false success -- but
that safety net itself is unconfirmed against real hardware, and the
risk noted in T-072 ("worse case, unknown") still applies to the first
live attempt.

## Criteria

- [ ] Run `fiedle400 -v clear -s 1 -y` against a real device holding a
      Manual-mode recording (expendable test data, not something that
      still needs the recording) and record exactly what happens with
      `--debug`/`-v` output
- [ ] If possible, also capture the real SpO2 Assistant's own Delete
      button against a Manual-mode recording, to compare against the
      static-analysis byte layout
- [ ] Update `PROTOCOL.md` §3.14 G from "static analysis only,
      unconfirmed" to the real result (confirmed layout, or a
      correction to it)
- [ ] If the real result differs from what `_clear_manual` sends, fix
      it; if it matches, remove the "not yet tried against a real
      device" caveat from the ticket/changelog history (next entry
      only, not the historical ones)
- [ ] Tests pass

## Execution Notes

(Not started.)
