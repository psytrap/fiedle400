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

- [x] Run `fiedle400 -v clear -s 1 -y` against a real device holding a
      Manual-mode recording (expendable test data, not something that
      still needs the recording) and record exactly what happens with
      `--debug`/`-v` output
- [x] If possible, also capture the real SpO2 Assistant's own Delete
      button against a Manual-mode recording, to compare against the
      static-analysis byte layout (done informally -- psytrap ran the
      vendor app's own erase and confirmed it works, but no packet
      capture was taken; byte-for-byte comparison is still open, see
      Execution Notes)
- [x] Update `PROTOCOL.md` §3.14 G from "static analysis only,
      unconfirmed" to the real result (confirmed layout, or a
      correction to it)
- [x] If the real result differs from what `_clear_manual` sends, fix
      it; if it matches, remove the "not yet tried against a real
      device" caveat from the ticket/changelog history (next entry
      only, not the historical ones)
- [x] Tests pass (411/411, unchanged by this round -- no code changed)

## Execution Notes

**Real-hardware confirmation (local, 2026-10-21).** psytrap independently erased a Manual-mode
recording with the real SpO2 Assistant app first (confirmed it works there), then made a short
test recording at 17:13:45 (142 samples, 2m22s) specifically so `fiedle400 clear` could be tried
against real data without risking anything that mattered.

`python3 -m fiedle400 -v clear -s 1 -y` against the real device:

```
[DEBUG OUT] Manual delete step 0x00 (0xA1): a1002100...
[DEBUG] Erase reply status: 0
[DEBUG OUT] Manual delete step 0x01 (0xA1): a1012200...
[DEBUG] Erase reply status: 0
[DEBUG IN] Manual header: ManualHeader(start=None, samples=0, kind=0)
✅ Erased Session #1 from the device.
```

`fiedle400 sessions` afterwards: "No stored recording sessions found" -- the recording is
actually gone, not just unlisted. This is the first real-device confirmation that `A1 00` then
`A1 01` (the static-analysis byte layout from patch 0033) is the correct Manual-mode erase: both
steps got a real `D1 ... 00` (status 0) reply, and the header query that used to return the
recording now returns nothing at all.

**Still open:** no packet capture of SpO2 Assistant's own Delete exists yet to compare
byte-for-byte against `manual.delete_step()` -- this result confirms `fiedle400`'s own sequence
works, not that it is identical to what the vendor app sends. Good enough to retire T-072/T-073's
core open question (`clear` on a Manual-mode recording now erases correctly on real hardware);
a byte-for-byte vendor capture would still be a nice-to-have, not pursued further here.
