# T-011: Check `.spo2` export compatibility against the real SpO2 Assistant

- **Status:** Open
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

- [ ] `SpO2.exe` is actually launched against a real `fiedle400`-written
      `.spo2` file (not just its strings/disassembly re-read again),
      and the result (opens cleanly / opens with wrong data / fails)
      is recorded, with the method used to run it.
- [ ] If SpO2 Assistant rejects or misreads the file, the specific
      byte/field responsible is identified against `SPO2_FORMAT.md`,
      and either a fix is filed as a follow-up ticket or the format
      doc is corrected to match reality.
- [ ] The reverse direction (does `fiedle400` correctly read a
      `.SpO2` file written by the real SpO2 Assistant, if such a file
      is available) is checked too, not just the write direction.
- [ ] `SPO2_FORMAT.md` §5.1's SpO2 Assistant compatibility claim is
      updated to say it was verified by execution (with date and
      method), matching the standard already applied to its OSCAR
      entry -- or, if it could not be run at all, the claim is marked
      explicitly as still static-analysis-only rather than left to
      imply more than was actually checked.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
