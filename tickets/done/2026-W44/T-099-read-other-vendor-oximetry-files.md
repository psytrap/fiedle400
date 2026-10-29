# T-099: Read the other vendor oximetry files (`.spoR`/`.spo`, 4-byte `.SpO2`)

- **Status:** Won't Do
- **Priority:** Normal
- **Owner:** Cloud
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Scope & Relevant Files:**
  - `fiedle400/recording.py` (`read_spo2_file`)
  - `SPO2_FORMAT.md`
  - `tests/` (synthetic files)

---

## Description & Context

T-061's actual ask: open a recording from another model in `view` and the HTML
viewer, without device support. This works without a device because the
formats are written down in OSCAR's source (`cms50f37_loader.cpp`
`readSpoRFile`, `cms50_loader.cpp` `readSpoRFile`; file filter
`*.spo *.spor *.spo2 *.SpO2`) and `SpO2.exe` has its own `.SpO2` reader
(`0x4E2277`). `read_spo2_file` today reads only the PO-400's 2-byte-record
`.SpO2`.

Differences OSCAR handles that `fiedle400` does not:
- `.SpO2` with more than 2 bytes per record: OSCAR derives the record size from
  the file size; the CMS50I writes 4 bytes (a 16-bit value, then SpO2, then
  pulse).
- `.spoR`/`.spo` (SpO2 Review, CMS50D+/E): header offset in the first `uint16`,
  start time as a UTF-16 `MM/dd/yy HH:mm:ss` string at byte 8 (empty on a
  CMS50D+, which has no clock), 2-byte records with pulse first, then SpO2:
  the reverse of `.SpO2` (OSCAR appends `OxiRecord(o2, pr)` there and
  `OxiRecord(pr, o2)` for `.SpO2`, with `OxiRecord(pulse, spo2)`).
- A zero date means "no clock"; OSCAR then uses today at midnight.

Without a real file this is built to OSCAR's and `SpO2.exe`'s readers and
tested with synthetic files. A real file from a PO-250/PO-300 owner (T-102)
confirms it.

## Criteria

- [ ] `.SpO2` record size taken from the file (2 or 4 bytes), as OSCAR does
- [ ] `.spoR`/`.spo` read, including the no-clock case
- [ ] An unknown layout fails with a clear message, not a traceback
- [ ] Synthetic test files for each case; `SPO2_FORMAT.md` documents the variants
      and marks them "from OSCAR's source, not yet seen in a real file"
- [ ] Tests pass

## Execution Notes

Dropped by psytrap (2026-10-29): "t99 is bullshit. download recording from device is the
task". Reading other software's files is not wanted; T-061 is now about downloading stored
recordings from the device (T-101).
