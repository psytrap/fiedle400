# T-082: Wizard reports erase succeeded, but the session is still there afterward

- **Status:** Open (deferred)
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`SerialDeviceEngine.clear_memory`, lines 728-784)
  - `fiedle400/cli.py` (`run_interactive_wizard`, erase step around line 1120-1122)

---

## Description & Context

psytrap ran the interactive wizard against a real device with an
Auto-mode recording. The wizard's "Erase recordings from device flash?"
step printed the success message (`✅ Erased ... from the device.`), but
the recording was still present afterward (not yet re-checked with plain
`fiedle400 clear`/`sessions` outside the wizard -- see Criteria).

This matters because `clear_memory`'s own success signal is not a
device ACK -- it writes the delete command(s), then immediately calls
`self.list_sessions()` *in the same connection* and returns `True` only
if the target no longer appears in that fresh listing
(`engine/device.py:778-784`). If that passed here, the device's listing
replied empty right after the write, yet the recording was back/still
there afterward. Either:

- the post-erase listing reflects a transient or cached state rather
  than what is actually committed to flash (the write needs more time,
  or a reconnect, before the device's own listing is trustworthy), or
- something specific to the wizard's flow (download immediately
  followed by erase, all within one open connection/handshake) leaves
  the device in a state where the erase command does not take, even
  though the immediate re-list says it did.

Not yet known which -- that's what needs isolating. This cycle already
has one open erase-reliability finding (T-074, single-session `-s N`
erase not accepted by the device at all, with an honest "still listed"
warning); this is different; here the *full* erase (session 0, the
path T-072/T-073 confirmed working) reports success and still doesn't
stick.

## Criteria

- [x] Reproduce without the wizard: `fiedle400 sessions`, then
      `fiedle400 clear` (full erase, no `-s`), then a **separate**
      `fiedle400 sessions` invocation (fresh connection) -- does the
      recording come back the same way?
- [x] Reproduce via the wizard itself (download -> erase, one open
      connection) with debug output, then a **separate** `sessions`
      check afterward
- [ ] Root cause identified and either fixed, or recorded as a known
      device limitation (like T-074) with the wizard/CLI no longer
      claiming success when it isn't durable -- blocked until it
      reproduces again (see notes)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

**2026-10-22, real hardware (Claude, at psytrap's request):**

- Backed up the 2 real stored sessions first (30,030 records total,
  session #2 had 162 checksum-failed frames dropped -- separate matter,
  not this ticket) to a local `.spo2` file, then ran plain `fiedle400
  -vv clear -y` against them. Erase reported success; a **separate**
  `fiedle400 sessions` process afterward showed none left. Worked, and
  persisted.
- psytrap recorded a fresh throwaway session (122 records, 2m02s) to
  test the actual wizard path. Drove the wizard non-interactively with
  `-vv`: listed the session, downloaded it (244 packets, 0 sequence
  gaps, clean), then answered "yes" to "Erase recordings from device
  flash?". Debug log shows `Delete All (0x9D 0x7F)` -> `Erase reply
  status: 0` -> "Erased the recordings from the device." A **separate**
  `fiedle400 sessions` process afterward again showed none left.
  Worked, and persisted.
- Could not reproduce "says erased, but still there" in either the
  standalone-`clear` path or the exact wizard download->erase path, on
  the same real device psytrap saw the original failure on. Both
  erased sessions this time are gone for good (no way to re-upload
  stored data to the device), so the specific combination psytrap first
  hit -- a bigger/messier multi-session download (the kind with
  sequence gaps and checksum failures, like the original 2-session
  data) immediately followed by a wizard erase -- was never actually
  exercised end-to-end here; only a small, clean single-session
  download went through the wizard.
- Leaving this open rather than closing it: psytrap did see the
  failure once, and intermittent real-hardware erase/USB quirks have
  turned up before this cycle (T-074, T-078). If it happens again,
  capture `-vv` output from that exact run (ideally right after a
  bigger/messier download) before re-erasing, so there is a log to
  compare against the two clean runs above.
- Built a "finger dummy" (phone vibration against the sensor, driven
  by a free online heartbeat-pattern vibrator) to generate throwaway
  test sessions without needing a real finger -- repeated use produced
  13 small sessions (460 records total). Ran the wizard end-to-end
  against all 13 with `-vv`: download succeeded (no sequence gaps),
  `Delete All (0x9D 0x7F)` -> `Erase reply status: 0` -> "Erased the
  recordings from the device." A separate `fiedle400 sessions` process
  afterward again showed none left. Third attempt, still no repro --
  now covering a multi-session (13-session) case too, closer to the
  messiness of the original 2-session failure, though still without
  that original run's checksum/sequence-gap errors.
- **Fourth attempt:** ran the wizard against 10 sessions built up via
  the T-083 wiggler rig, including a 1h25m/5,103-record session -- the
  first attempt here with a long, substantial single session rather
  than only short test clips. Download clean (6,734 records, 0
  checksum failures, 0 sequence gaps), erase reported success, and a
  separate `fiedle400 sessions` process afterward again showed none
  left.
- **Correction (same day):** re-examined what actually happened at the
  start of this investigation. The very first `fiedle400 sessions`
  check here found the *same* 2 real sessions (36m07s + 7h44m23s)
  psytrap had already run the wizard against -- i.e. that data being
  still present *was* the original failure sitting there live, not
  fresh pristine data. Backing it up and running plain `fiedle400
  clear` on it then erased it successfully. So on that one exact
  dataset: **wizard (download -> erase) failed to persist; standalone
  `clear` on the same data worked.** That's a real, direct contrast,
  not a coincidence.
- That dataset is also the only one involved here that hit checksum
  failures/sequence gaps during download (162 failed frames, 2,864
  gaps on the 7h44m/27,863-record session -- see
  [T-084](T-084-download-checksum-failures-on-long-sessions.md)).
  None of the four "clean" repro attempts logged above had any
  download errors at all -- so they were never actually recreating
  the one condition the original failure had. Retracting the "four
  straight clean attempts, probably not duration-dependent" read from
  earlier: those attempts just never reproduced the messy-download
  precondition, so they don't prove much either way.
- Working theory now: a download with real checksum/sequence-gap
  corruption, immediately followed by the wizard's erase step in the
  same open connection, is what fails -- not full erase in general.
  T-082 and T-084 may be one root cause, not two. Since the checksum
  errors only showed up on a session ~8x bigger by packet count than
  anything generated via the T-083 wiggler rig so far, provoking it
  again likely needs a much longer (many-hour) recording, same as
  T-084's next step -- not because erase itself is duration-sensitive,
  but because the messy download that seems to trigger it is.

**2026-10-22, later (Claude + psytrap, on two fresh 1-minute Auto-mode
recordings):** Separately, psytrap flagged that `list_sessions()` is
known to come back empty sporadically -- distinct from this ticket, see
[T-085](T-085-clear-poll-timeout-retry.md) for that fix (retries an
empty result up to 3x before trusting it). Two reliability passes run
against the real device to sanity-check the surrounding machinery
before chasing this ticket's exact bug further:
- 100x open-connection / `list_sessions()` / close, on a device with 2
  known non-empty sessions: 0/100 empty (neither the raw nor retried
  path), consistent session count every time.
- 100x full interactive wizard (download all -> save -> **answer "no"
  to erase**), same 2 sessions kept in place for every pass: 100/100
  clean -- same 113 total records, 0 sequence gaps, "Flash recordings
  preserved" every single time.

Neither test exercises the erase step itself, so they don't touch this
ticket's actual bug -- they just confirm the listing/download path
around it is solid. psytrap then tried to reproduce the erase failure
manually (wizard with erase answered "yes") and again **could not
reproduce it** -- consistent with every attempt so far except the one
original real occurrence. Still leaning on the "messy/checksum-heavy
download" precondition (see above) as the missing ingredient none of
these attempts have had.

**2026-10-25, the exact precondition finally reproduced, still no
repro of this ticket's bug:** A real device accumulated 4 sessions
including a genuine ~7h31m/27,066-record one. Ran the Download Wizard
(download all -> erase) with `-v` debug against it: session #4 hit the
checksum/sequence-gap corruption again (161 bad frames, 2,704 gaps --
see [T-084](T-084-download-checksum-failures-on-long-sessions.md)), and
erase was issued immediately afterward in the same connection -- this
is the exact "messy download immediately followed by erase, same
connection" precondition the working theory above describes, finally
produced on demand rather than only seen once historically. `Delete All`
-> `Erase reply status: 0` -> re-list came back empty (after 2 retries,
expected per T-085's retry logic) -> "Erased the recordings from the
device." A **separate**, fresh `fiedle400 sessions` process run
afterward confirmed **0 sessions** -- erase persisted correctly this
time.

So the precondition this ticket's working theory pointed at has now
actually been tested, twice in the same session (this run, plus the
plain interactive download+no-erase run just before it), and the bug
still did not reproduce. This weakens (without disproving) the
messy-download-triggers-bad-erase theory -- worth considering whether
the original occurrence was something else entirely (a one-off USB/
device hiccup unrelated to data quality), especially alongside T-078's
documented transient first-command flakiness.

**2026-10-25, preventive fix applied regardless:** Even without a
confirmed root cause, psytrap asked for a simple mitigation rather than
waiting for another repro: `clear_memory` now waits
`ERASE_SETTLE_SECONDS = 3.0` (up from an implicit ~0.5s) right before
its post-erase re-list, instead of checking almost immediately. No poll
loop, just a longer flat settle delay -- see
[T-085](T-085-clear-poll-timeout-retry.md) for the implementation. The
reasoning: `_erase_status()` validates its reply's checksum before
trusting it (`device.py:850-862`), so a corrupted/misread *command* is
an unlikely explanation; a stale/not-yet-committed flash state at the
moment of the re-list is the more plausible mechanism, and a longer
settle window directly addresses that without needing to know exactly
why. Full suite passes (423 tests); not yet verified against a real
erase (no device connected at the time). Root cause still not
confirmed -- leaving this ticket open until either it recurs (now with
the longer delay in place, to see whether that alone fixes it) or
enough clean runs accumulate to downgrade it to a known, unreproduced,
possibly-already-mitigated issue.
