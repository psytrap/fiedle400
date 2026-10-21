# T-037: `fiedle400 clear`'s per-session erase sequence is unverified against a real capture

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (the `clear` command's byte sequences)
  - `PROTOCOL.md` §3.13 (`FLASH_CLEAR`)

---

## Description & Context

`PROTOCOL.md` §3.13 documents the vendor's erase opcodes (`0xAA` full erase,
`0x91`..`0x96` per-user erase) from the `SpO2.exe` disassembly, but notes none
of them has ever been captured in a real recording.

`fiedle400 clear` in `engine/device.py` does not send those documented bytes.
It sends a different, undocumented sequence: `0xAF`, then either `0xAB 01
[id]` for a single session or `0xAA 80 80` / `0xAB 80 80` / `0xAC 80 80` for
all sessions, each with the `7D 81` prefix. `PROTOCOL.md` already flags this
as "none of this is documented or recorded; treat `clear` as unverified."

What is NOT known:
- Whether `0xAB 01 [id]` actually erases only the named session, erases more
  than that, or does something unrelated -- there is no capture of it
  succeeding, partially succeeding, or failing.
- Whether the `0xAA 80 80` / `0xAB 80 80` / `0xAC 80 80` "all sessions" forms
  behave as their naming implies.

This matters because `fiedle400 clear` is a destructive, user-facing command
run against real device flash holding real recorded sessions -- unlike
`download`/`sessions`/`info`/`selftest`, which are read-only per `AGENTS.md`.

## Safety

- Never erase device flash as part of investigating this ticket without the
  owner's explicit, informed go-ahead for that specific run, and only against
  sessions that are not needed (or are backed up first via `download`).
- No automated test may send any of these sequences to a real device.

---

## Criteria

- [x] A written recommendation on how to verify `clear`'s actual behavior
      safely (e.g. a disposable test recording, captured with
      `record_exchange.py`, erased deliberately with explicit consent) --
      or a decision to leave it unverified for now, with a reason.
- [x] If verified: `PROTOCOL.md` §3.13 updated with the real behavior and a
      capture reference; if not verified: the "unverified" note stays as-is.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**Done (Claude, cloud, 2026-10-21, patch 0031).** psytrap decided: "clear is erase, use the 9D
command". `clear_memory` now lists the recordings, sends `9D 02` like the vendor tool, then
`9D 7F 7F 7F 7F 00 00 19` (all) or `9D 7F 02 [user] [entry] 00 00 [chk]` (one), and lists them
again: `clear` and the wizard say whether the recordings are gone. A Manual-mode recording is
not erased this way (the vendor gates `9D 7F` to Auto mode). `tests/test_clear.py` checks the
bytes against the vendor capture. The erase-all is confirmed by the vendor captures; running
`clear` on a device, and delete-one at all, is in `tickets/INDEX.md`, "Open questions".

**Findings so far (Claude, cloud, 2026-10-20/21, patch 0030; static analysis of `SpO2.exe`,
checked against every vendor capture).
The ticket stays open: verifying on the device is the local step.** Details are in
`PROTOCOL.md` §3.13.

- **The vendor's delete commands for this device:**
  - `9D 7F 7F 7F 7F 00 00 19` deletes every recording. It is sent by the "Delete All" button and
    by the automatic delete after saving (`0x4af695`).
  - `9D 7F 02 [user] [entry] 00 00 [chk]` deletes one recording. It is sent by the "Delete"
    button, once per selected recording (`0x4af43c`). `user` and `entry` are bytes 2 and 3 of
    its `0xEC` header (T-039).

  The buttons are in the "Device Stored Data" dialog (resource 148).
- **`0xAA` and `0x91`..`0x96` are not deletes.** `SpO2.exe` never sends `0xAA`. `0x91`..`0x96`
  are transfers for another kind of stored data, answered by `0xE1`..`0xE6`.
- **`fiedle400 clear` matches nothing the vendor sends.** It sends `0xAF`, then `0xAB 01 [id]`
  for one session, or `0xAA`/`0xAB`/`0xAC 80 80` for all. It may do nothing at all. The same
  method backs the wizard's "Erase recordings from device flash? [Y/n]", so that prompt may not
  erase anything either. Whether a recording was still listed after an erase from the wizard
  would tell.
- **The erase-all is confirmed by the vendor captures.** Five of the six captures end with
  `9D 7F 7F 7F 7F 00 00 19` (what `PROTOCOL.md` used to call `STORAGE_FINALIZE`), and each
  following capture starts again at entry 1 with only newer recordings (`PROTOCOL.md` §3.13).
  None of the captures contains `9D 7F 02` or any of `fiedle400 clear`'s bytes.
- **Guards added in 0030:**
  - The `hwsim` fake now counts any `9D 7F ...` as destructive.
  - The unused `storage_finalize` builder says what it really is.

**Recommendation for the local check:**
1. Make two short throwaway recordings. Back them up with `fiedle400 download -f spo2`.
2. Turn the auto-delete off in SpO2 Assistant if it has the setting
   (`bAutoDeleteSegmentSaveData`).
3. Delete one recording with its Delete button, capturing with `tests/capture_tools`. Then
   `fiedle400 sessions` should list one recording.
4. Separately, check whether the current `fiedle400 clear` changes anything. Delete All needs no
   new run: the captures already show it.

Only with your go-ahead for each run.
