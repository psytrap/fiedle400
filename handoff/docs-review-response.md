# Docs review: response (patch 0015)

Answer to `handoff/docs-review.md`. Base: device HEAD `014bfcf` (0.3.6); all 81 tracked files were
re-staged and match. One patch, as asked: the docs review, the code fixes it called for, and fixes
to the agent instructions. Version 0.3.7; 259 tests pass (7 skipped), pyflakes clean.

**Method.** Every byte-level claim in `PROTOCOL.md`, the German mirror and the bum400 write-up was
checked against the three recordings in the repo: the vendor capture
`analysis/bum400_20260906_100516.pcap` (all 271 reports replayed, every frame's checksum checked) and
the CLI's real-device traces `tests/fixtures/cli-exchange.trace.json` and `probe.trace.json`. A claim
with no recording behind it is now marked "from the disassembly only" instead of being stated as fact.
The bum400 §6 table (122 records) matches today's decoder value for value.

## Corrected in the patch (evidence-backed, non-Manual sections)

`PROTOCOL.md`, mirrored in `analysis/po400_bytemap_reference.md`:

1. **`0xEC` header is 21 bytes, not 64.** User name `0x0E..0x13`, checksum at `0x14` (`0x42` vendor,
   `0x03` CLI, both verified), then zeros. §2.2 already said 21 B; §3.2 contradicted it.
2. **Record count is `(raw + 1) // 2`, not `raw // 2`.** The vendor header says 243 and the session
   has 122 records; the code already does this (0013), the docs said `// 2`.
3. **`0xEF` geometry follows `9F 1F`, not `8F 04 00 13`.** The device answers `8F 04 00` with
   `FF 00 7F`. `info` sends `9E 40 04` and gets an ACK, which is why geometry shows "not reported".
4. **`80 00` (firmware) gets a bare ACK**, 3x in the vendor capture and in the probe trace. The `0xCF`
   / "V3.1" reply was never on the wire; the T7 note now lists `0x80` too.
5. **`0xFE` replies have three lengths**: `8E 03` -> 10 B (`"   user"`, checksum at `0x09`), `8E 06` ->
   7 B, `8E 07` -> 5 B with **no serial number**. The documented 11-byte layout fits none.
6. **`9D 02 ...` (init/ack) gets no reply** in any recording (docs said `0xF0`), and the vendor sends
   it as 8 bytes with the checksum at `[0x07]`; the §3.5 table had it at `[0x08]`.
7. **`SET_RTC` is answered `F3 00 73`**, not `0xF2`/`0xF0`. The vendor's bytes match the documented
   layout exactly.
8. **`0xF2` never changes**: `F2 00 00 02 07 00 0C 07` on 2026-09-06 before and after a clock set,
   and on 2026-10-15. It is not a live clock reading. The README's "device reads 2002-07-01" is our
   parser reading this from byte 3 (the minutes are the checksum byte). README, DESIGN and the
   release-notes text in `build-release.yml` now say the device does not report its clock.
9. **Reply-length facts** added to §1/§2.2: two accepted request framings (bare vs `7D 81`), replies
   are self-delimiting frames ending in a checksum, several can share one report.
10. **§3.5 offsets**: "single request at offset 0 for the whole series" contradicted the 937-record
    multi-reply download; now "continue where the reply ended". "All three masks are `7F`" on the last
    frame is wrong (`70 7F 7F`, `78 7F 7F`, vendor `00 00 60`). The recorded end marker
    (`ED 04 01 00 00 7B 7F 7F ...`, mode `04`) is added next to the disassembly's `mode 00` sentinel.
11. **Finger-out wording**: 127/255 are what `SpO2.exe` writes for out-of-range *decoded* values
    (bum400 §A.5) and the `.SpO2` file's sentinels, not observed wire values. Matches T1 being open.
    Same fix in `AGENTS.md` (invariant) and `DESIGN.md` §3.
12. `0xEB` live stream: the only recording shows 6 B, 8 B and 3 B frames whose length follows byte 1,
    so byte 1 looks like a frame type (as `parse_hid_chunks` treats it), not a status bitfield. Noted,
    table left as is.
13. Marked as not in any recording: `0x94`/`0xD4`, the `0xE0` alarm map (recorded reply is 15 B and
    doesn't fit), `0xCF`, erase commands. `0xA5`/`0xA6` note: no reply on this firmware (CHANGELOG).
14. §3.13: the unmodified vendor tool erases (`0x91..0x96`) after every download (bum400 §A.6);
    `fiedle400 clear` sends undocumented bytes (`0xAF`, `0xAB`, `0xAC`, `0xAA 80 80`); a mode switch
    on the device erases too.
15. German only: the old two-report handshake with checksums `0x20`/`0x1B` replaced by the one-write
    form; the read-offset bytes renamed from "Subframe" to raw-sample offset; a note at the top says
    `PROTOCOL.md` is authoritative. File keeps its CRLF line endings.

`analysis/bum400_20260906_100516.md`: working notes, so not rewritten. A dated note at the top lists
where they disagree with the capture (header length, missing/mislabelled commands in §2, sentinels,
§A.6's "0x8E 3/6/7 deletes", which the same capture contradicts in that order of use).

**Cross-references** (after the RELEASE_PLAN/CHANGELOG split):
- T-number pointers in PROTOCOL.md, tests/capture_tools/README.md and AGENTS.md now go to `CHANGELOG.md`.
- RELEASE_PLAN.md and CHANGELOG.md gave the T8 repro as `fiedle400 selftest -b hid`, which fails
  ("unrecognized arguments"). It is now `fiedle400 -b hid selftest`. CHANGELOG also wrongly said there
  is no `--backend` long form.
- CHANGELOG cited a PACKAGING.md phrase that 0014 removed; it now points to the README.
- RELEASE_PLAN had the v0.2.17 process-gap warning twice (§2 and §3d); the §3d copy is now a pointer.
- RELEASE_PLAN §3e: two TODOs still said "Not yet done"; both are marked delivered in 0014.
- AGENTS.md glossary: gates are G1..G8, not G1..G7.
- Left as is (your decision): RELEASE_PLAN §2 says G7 passed on 2026-10-15 and the release is ready
  to promote from alpha, but `build-release.yml` (comment at line 226, release body at line 234) still
  says "Alpha release ... G7 not done". Promoting means flipping that text and `prerelease`.

## Flagged, not changed: Manual mode (§3.14 and the German mirror)

Per AGENTS.md these stay as they are. Nothing in them can be checked here, because **no Manual-mode
capture is in the repository**. Committing one (as a fixture or in `analysis/`) would let the next
pass verify instead of flag.

- M1. **Contradiction in framing.** English §3.14.B: one 64-byte report holds exactly three 20-byte
  subframes plus 4 padding bytes. German §B: a continuous chain of 20-byte subframes that is *not*
  aligned to reports, so a subframe can span two. An implementation must pick one.
- M2. Header example differs: English `13 22 10` / `00 00 3B` (19:34:16, 59 s), German `13 31 0C` /
  `00 00 29` (19:49:12, 41 s). Probably two recordings; English (c) then mixes 41 s with 59 samples.
- M3. **Opcode `0xA7` is reused too**, not only `0xA2`: the block ACK `A7 00 27` / `A7 01 28` shares
  the unlock opcode. The reuse warning names only `0xA2`.
- M4. **Safety:** neither version says that switching Auto/Manual on the device erases its memory
  (CHANGELOG, vendor dialog text). Worth a caution in both.
- M5. The English registry (§2.1) has no Manual-mode rows; the German one does. I added a pointer
  line to §3.14 instead of rows.
- M6. Stale pointer in the §3.14 intro: "RELEASE_PLAN.md §3d" (that story is now in CHANGELOG.md).
- M7. Small asymmetries: German lacks (d) (`0x7F` vs a `+7, -7` pair) and the "typical exchange";
  English lacks the `cmp edx, [this+0x120]` detail from German (c).

## Code fixes in this patch

- **Clock (`read-time`, `info`, wizard).** The `0xF2` reply is no longer decoded into 2002-07-01.
  `read-time` prints the raw reply and says the clock is not reported; `info` and the wizard say
  "not reported by the device". The detector now takes the reply as 8 bytes (it took 10, two past
  the checksum). `read_rtc_time()` returns the raw reply; `parse_rtc_response` is gone.
  **Live test changed:** `test_device_live.test_05` now expects exactly `f2 00 00 02 07 00 0c 07`.
  If it fails on your device, the device does report its clock after all: please record it.
- **Wizard defaults.** The wizard printed "v2.0", "50F" and "CMS-50F" when the device sent
  nothing. It now prints "not reported by the device" (AGENTS.md invariant).
- **`selftest -b hid`** now works, like the other commands. RELEASE_PLAN and CHANGELOG updated.

Not changed, with the reason:
- `info` geometry via `9F 1F`: the `0xEF` fields are undecoded, so it would only print raw bytes.
- `set-time` layout: the vendor's layout is recorded, but changing it is a device write that needs
  a live test first. Say if you want it, and run `set-time` + a new recording after.
- Init/ack (`9D 02`, 9 vs 8 bytes) and stop-stream bytes differ from the vendor's; harmless so far.
- `clear` uses unrecorded opcodes; nothing to change without a deliberate test on an empty device.
- `0xEC` bytes 2/3 (user/session vs segment count/index): needs a recording with 2+ sessions.

## Instruction fixes (`AGENTS.md`, `.agents/rules/`)

- Delivery: one patch per request, findings and their fixes together, follow-ups merged into a
  patch that is not applied yet. A patch that changes product code bumps the patch version.
- New invariant: never show a default for a value the device did not send.
- CRLF/NUL warning for `analysis/*.md`; `CHANGELOG.md` added to the source-of-truth list; the
  `handoff/` glossary entry now says where answers go.
- `implausible_data_warning.md`: 127/255 described as vendor sentinels for out-of-range decoded
  values (not wire values, T1 open); the unrecorded flag bytes (`0x30`, `0x10`, `0x0F`) removed.

## Recordings that would settle the open points

- A device holding 2+ sessions (bytes 2/3 of `0xEC`, and how many samples one reply holds).
- A live stream with a finger on (the `0xEB` field map).
- A stored session with a finger-out stretch (T1).
- The Manual-mode exchange (M1, M2).
