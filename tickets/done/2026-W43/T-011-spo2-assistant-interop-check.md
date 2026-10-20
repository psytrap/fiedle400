# T-011: Check `.spo2` export compatibility against the real SpO2 Assistant

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/export.py` (the `.spo2` writer)
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local
    artifact -- the real vendor Windows application, not just its
    strings this time)
  - `SPO2_FORMAT.md` §5.1 (the existing, *unverified-by-execution*
    compatibility claim)
  - `archive/capture/` (existing real `.SpO2` captures to cross-check)

---

## Description & Context

psytrap: check whether `.spo2` files `fiedle400` writes are actually
compatible with **Contec SpO2 Assistant**, the real vendor Windows
application -- not the static analysis already done.

**What's already been checked, and what hasn't.** `SPO2_FORMAT.md`
§5.1 states SpO2 Assistant "Validates `magic == 0x358` (856) and
parses start date/time block at offset `0x0420`" -- but per that same
section's OSCAR entry, the *OSCAR* claim was explicitly re-verified
against OSCAR's real source in a dated note; the **SpO2 Assistant**
claim carries no such note. It traces back to the string/offset mining
of `SpO2.exe` done for T-007 (`archive/bruteforce/FINDINGS.md`),
i.e. reverse-engineered from the binary's own validation code path,
not from actually running `SpO2.exe` and opening a file `fiedle400`
produced. That is a meaningfully weaker form of evidence than T-007's
own standard for itself ("a label shows that a feature exists, not
how it works") -- here it's "a validation check was seen in the
disassembly," still short of "the exe actually opened our file."

**What this ticket is for:** close that gap by actually running
`SpO2.exe` (Wine on Linux, or a real/virtual Windows machine) against:
1. A `.spo2` file `fiedle400` wrote from a real downloaded session
   (`fiedle400/export.py`'s output) -- does SpO2 Assistant open it
   without error and show the right session length / start time /
   trace?
2. A `.SpO2` file SpO2 Assistant itself produces (or one of the
   existing captures already in `archive/capture/`) -- does
   `fiedle400`'s own reader (wherever `.spo2` is parsed back, if
   anywhere) round-trip it correctly?

**Known constraint worth flagging up front, not discovering mid-way:**
`SpO2.exe` is a GUI Windows PE32 binary. If Wine isn't viable in
whatever environment runs this (headless, no X server) the same
Xvfb-for-a-GUI-app problem applies here as to any other native GUI
testability question raised this session -- this ticket's own
Execution Notes should record which environment/method was actually
used (real Windows machine, Windows VM, Wine+Xvfb, or "could not run
it, falling back to static re-analysis") rather than silently skipping
the live check if it can't be done.

---

## Criteria

- [x] `SpO2.exe` is actually launched against a real `fiedle400`-written
      `.spo2` file (not just its strings/disassembly re-read again),
      and the result (opens cleanly / opens with wrong data / fails)
      is recorded, with the method used to run it.
- [x] If SpO2 Assistant rejects or misreads the file, the specific
      byte/field responsible is identified against `SPO2_FORMAT.md`,
      and either a fix is filed as a follow-up ticket or the format
      doc is corrected to match reality.
- [x] The reverse direction (does `fiedle400` correctly read a
      `.SpO2` file written by the real SpO2 Assistant, if such a file
      is available) is checked too, not just the write direction.
- [x] `SPO2_FORMAT.md` §5.1's SpO2 Assistant compatibility claim is
      updated to say it was verified by execution (with date and
      method), matching the standard already applied to its OSCAR
      entry -- or, if it could not be run at all, the claim is marked
      explicitly as still static-analysis-only rather than left to
      imply more than was actually checked.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**Method.** Real Windows 8.1 laptop (`192.168.2.165`), reached over SSH
(`~/.ssh/po400_win_ed25519`), real SpO2 Assistant GUI -- not Wine, not a VM.
Files exchanged via `scp` through the same key. The real PO-400 device was
connected locally during this work, so the write-direction test used a real
downloaded recording, not a synthetic one.

**Direction 1: write (`fiedle400` -> SpO2 Assistant).** Two real device
sessions (2026-10-16, 08:37:31 + 2m40s and 08:43:12 + 30s) downloaded with
`fiedle400 download --all -f spo2` and opened in the real SpO2 Assistant:

- First attempt (pre-T-020-fix code): opened cleanly, no error, but showed
  one continuous 3m10s recording -- which led directly to filing and fixing
  **T-020** (the multi-session gap-collapse bug found via this ticket's own
  testing, not a pre-existing finding).
- Re-tested after T-020's fix (v0.4.21): same two sessions re-downloaded,
  opened in SpO2 Assistant, reported **6:11** total duration (371 s: 160
  real + 181 sentinel-padded gap + 30 real) -- exact match to the real gap.

In both cases **the file opened without error** -- SpO2 Assistant's own
validation of magic/version/header offsets accepts `fiedle400`'s output.
No byte/field rejection or misread was found; the only issue was the
(now-fixed) multi-session timestamp compression, which is a `fiedle400`
writer correctness issue (T-020), not an SpO2 Assistant compatibility
rejection.

**Direction 2: read (SpO2 Assistant -> `fiedle400`).** `fiedle400/plot.py`'s
`read_spo2_file` (the only `.spo2` reader shipped in the package) decoded a
real vendor-written capture, `archive/capture/_user_1_0_20260903074127-
20260903074137joint.SpO2`: start `2026-09-02 22:32:31`, 11480 records,
matching the file's own timestamp span exactly (`(end - start) + 1 ==
11480`). Values decoded are physiologically plausible (SpO2 90-97%, HR
56-82 bpm) across the sample shown. No decode error, no garbage values.

**`SPO2_FORMAT.md` §5.1 updated** (see diff in this commit) to state the
SpO2 Assistant compatibility claim was verified by execution on 2026-10-20,
with the method above, matching the existing standard set by the OSCAR
entry -- it previously carried no such note and traced only to static
string/disassembly mining (T-007's `FINDINGS.md`).

**Result:** `fiedle400` and the real Contec SpO2 Assistant are compatible in
both directions, write and read, verified by actually running the vendor
program -- not re-reading its strings. The one real defect this testing
surfaced (T-020) was found, fixed, and independently re-verified against
the real program before this ticket closed.

Broader coverage (more/longer real recordings, the other existing captures
in `archive/capture/raw/` and `archive/capture/realtime/`, a recording with
real finger-out data) is deliberately not required here -- this ticket's
own criteria only asked for one real check per direction, which is done.
That broader coverage is deferred as its own ticket, **T-021**, rather than
reopening this one.
