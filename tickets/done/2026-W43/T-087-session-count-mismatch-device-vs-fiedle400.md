# T-087: Device's on-unit "51 Seg" display vs. `fiedle400 sessions` listing only 31

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`list_sessions` / session enumeration)

---

## Description & Context

While checking a long (~8h) recording for download/checksum reliability
(see [T-084](T-084-download-checksum-failures-on-long-sessions.md)),
`fiedle400 sessions` and `fiedle400 download` both consistently found and
listed exactly **31** sessions, stable across repeated checks (before and
after a full download). The device's own on-unit display, read directly
off the device by psytrap, precisely reads **"51 Seg"** (first read as 52,
then confirmed as 51 on a second look) -- a persistent gap of ~20 against
`fiedle400`'s count, not a timing fluke from new sessions landing
mid-check. "Seg" is presumably the device's own term for "segment" --
worth confirming whether that's the same unit as what `fiedle400` calls a
session, or something more granular (e.g. a lower-level chunk/block count
rather than one per recording), since that would change what the "gap" of
~20 actually means.

The large number of sessions in the first place is itself expected to be
an artifact of the [T-083](T-083-arduino-servo-test-fixture.md) wiggler
test fixture: its unreliable grip/contact is suspected to cause repeated
probe-out/probe-in transitions that split what should be one continuous
recording into many short ones. That explains *why* there are dozens of
sessions, but not why `fiedle400` and the device disagree on how many
there are -- of the 31 sessions `fiedle400` did list and download, every
one came back with 0 sequence gaps and no checksum failures, so this
looks like an enumeration/discovery gap rather than a data-corruption
issue like T-084.

## Criteria

- [x] Confirm what the on-unit "Seg" counter actually counts (same unit
      as a `fiedle400` session, or something more granular) -- **confirmed
      1:1 with a `fiedle400` session: at 99 sessions the device's own "99
      Seg" display matched exactly**
- [x] Check whether `list_sessions`'s enumeration loop has a fixed cap,
      an early-stop condition, or an off-by-N that would explain stopping
      at 31 when more exist -- **found: see Execution Notes**
- [x] Raise or remove the 31-slot cap and re-test against a device with
      more than 31 sessions to confirm it actually finds them all --
      **cap raised to 127 (the protocol's real 7-bit index limit);
      confirmed on real hardware at 99 sessions, matching the on-unit
      "99 Seg" display exactly**
- [x] Investigate the early-break/late-arrival oddity logged below --
      **fixed in the same change, see Execution Notes**
- [x] Decide whether this is more likely tied to the fixture-induced
      short/rapid-fire sessions specifically (e.g. a session boundary
      case `list_sessions` doesn't handle) rather than a general count bug
      -- **general bug, not fixture-specific: the 99-session confirmation
      run was a normal fill-up, not a wiggler-fixture artifact, and the
      fix (slot cap) holds regardless of session size/shape**
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      **423 tests, OK**

## Execution Notes

**2026-10-24:** Opened per psytrap's report. Full download of the 31
sessions `fiedle400` sees: 31/31 succeeded, 23,344 records total, 0
sequence gaps, 0 checksum failures logged across the whole run -- so the
31 sessions it does find are clean. The question is only about the
remaining ~20 the device claims to have.

**2026-10-24, root cause found:** Ran the interactive wizard's `[C]
Clear` path with `-v` packet debug while a fresh, differently-sized
batch of sessions was on the device (erase has since been run, so this
batch is now gone -- see below). Found
[`fiedle400/engine/device.py:515`](../../fiedle400/engine/device.py#L515)
(`_list_sessions_once`):

```python
for slot in range(1, 32):
```

This caps session discovery at **31 slots, hardcoded** -- it cannot
report more than 31 sessions no matter how many the device actually
holds. This lines up exactly with `fiedle400` consistently stopping at
31 while the device's own display read higher. This is very likely the
primary root cause; the on-unit "Seg" unit still needs confirming, but a
fixed query ceiling fully explains a flat 31 regardless of what the
device has.

Separately, in that same debug log: `_list_sessions_once` printed "Found
1 recorded session(s)" after reading only one `SESSION_INDEX` packet,
but 14 more (`SESSION_INDEX` for session ids 2..15, hex payload bytes
`ec0001` + id) showed up in the log later, between the main menu and the
`Delete All` command. Per-slot read timing is only `time.sleep(0.05)`
before `read_packets()` (line 517); on a device with many sessions
queued, a slow response can mean the slot read comes back empty, which
the `break` at line 522-523 treats as "no more sessions" and ends the
loop early. The device's remaining queued responses then drain in
later, unrelated reads (surfacing elsewhere in the log instead of being
counted). This looks like a second bug in the same function, likely
worth fixing alongside the 31-slot cap.

Erase (`[C]` path, same session) was run afterward and succeeded
cleanly -- `fiedle400 sessions` now reports 0 sessions, confirmed.

**2026-10-24, fix applied:** In
[`fiedle400/engine/device.py`](../../fiedle400/engine/device.py),
`_list_sessions_once`'s slot loop now runs `for slot in range(1,
MAX_SESSION_SLOTS + 1)` with `MAX_SESSION_SLOTS = 127` -- per psytrap,
the protocol's index byte only has 7 usable bits (0..127), the 8th
being reserved for command/flag data, so 127 is the real protocol
ceiling, not an arbitrary safety number. Real termination is still the
0x40 terminator bit, or a slot with no response. Each slot now
retries its read up to `SLOT_READ_ATTEMPTS = 3` times (0.05s apart) before
being treated as "no more sessions", fixing the early-break/late-arrival
issue from the same debug log (a single slow response used to end
discovery prematurely). Both constants added near the top of the module.
Full suite: 423 tests pass, no regressions (mocked test devices answer
immediately, so the extra retry attempts are never exercised there
except on the intentional "no more sessions" case, where they just
confirm emptiness a couple more times at no behavioral cost).

Not yet verified against a real device with more than 31 sessions, since
the test device was already erased by the time this was found -- the
device only had 31 (or fewer) sessions throughout the session that
produced the "51 Seg" report, so this fix has not been proven against
real hardware yet. Re-test next time the device accumulates a batch
that large.

**2026-10-25, confirmed fixed on real hardware:** Device filled up and
reported memory full. `fiedle400 sessions` now reports **99** sessions --
psytrap confirmed the on-unit "99 Seg" display matches exactly. The
31-slot undercount is resolved; the discovery loop correctly continues
past the old ceiling.

Followed up with two full end-to-end runs against this 99-session
device, both with `-v` debug:
- **Interactive download (no erase):** all 99 sessions downloaded,
  10,740 records total, 0 sequence gaps and no checksum failures logged
  anywhere -- also relevant to
  [T-084](T-084-download-checksum-failures-on-long-sessions.md).
- **Download Wizard, download + erase:** same 99/99 clean download,
  then `Delete All` issued (reply status 0); the post-erase re-list
  correctly came back empty (using the retry-on-empty logic added
  earlier, 2 empty attempts before trusting it), and `fiedle400 sessions`
  confirmed 0 sessions afterward. No sign of
  [T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md)'s
  "reports success but persists" symptom at this session count/size.

The 31-slot cap is confirmed fixed, on a device with over 3x the old
ceiling, in both the plain-download and full-wizard-erase code paths.
