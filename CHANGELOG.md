# fiedle400: Changelog & Investigation Log

The detailed hardware-investigation history that used to live in
`RELEASE_PLAN.md` §3d. Moved here 2026-10-16 to keep that file focused on
current status and open work; this file is the historical record of how
each finding was discovered, tested, and (mostly) fixed. `RELEASE_PLAN.md`
keeps a short, live summary and points here for the full story.

---

## 0.4.26 (2026-10-20)

**Breaking CLI change (T-012, psytrap's decision):** `fiedle400 download` now writes the
self-contained HTML viewer page by default, and **no `.spo2` is written unless asked for**.
`-f spo2|csv|json` (or an `-o` name with that extension) still gives the old files; the
wizard's format menu is now `[1] html (default) [2] spo2 [3] csv [4] json`, and after saving
an html page it asks "Open it in your browser now? [y/N]" (default no). Non-interactive
`download` never opens a browser. Scripts that relied on the `.spo2` default must pass `-f spo2`.

- **T-013:** new `fiedle400 view [FILE]` shows an existing `.spo2`/`.csv`/`.json` recording in
  the viewer (temporary page, no file left behind; `--convert [-o OUT]` writes `<recording>.html`
  instead). The readers moved from `plot.py` to the stdlib-only `recording.py`.
- **T-006:** `fiedle400 plot`, `plot.py`, `plot_session` and the `fiedle400[plot]` extra are
  removed; matplotlib is no longer bundled or installed in CI (expected binary saving: about 35 MB,
  RELEASE_PLAN B1b). The viewer has no 95/90 % and 60/100 bpm reference lines; it has a print
  button instead of the PNG.
- **T-027:** `tests/test_desat_js_parity.py` runs the viewer's JS detector under Node and compares
  it with `desat.py` (skipped without `node`). It found real drift: the JS rounded with
  `Math.round` (half-up, inexact `v * 100`) where Python's `round` goes to the even digit on exact
  ties, so values such as an average event duration of 10.25 s showed as 10.3 instead of 10.2.
  The JS now rounds exactly like Python.
- **T-031:** Basal SpO2's rule decoded from `SpO2.exe` (`0x54ced1`-`0x54d059`): the mean of the
  valid samples outside every event's fall, which is what `desat.py` already computed. The
  viewer drops the "(estimate)" label; when nothing is left outside events the value is now
  n/a instead of the mean of all samples. SPO2_FORMAT.md §7.1.
- **T-029:** pulse-rate events decoded: SpO2 Assistant runs the same detector on the pulse rate
  (6 bpm / 8 s, range 0..254), so only falls count. `desat.detect_pulse_events`; not shown in
  the viewer yet (T-030). SPO2_FORMAT.md §7.3.
- **T-035** (Local, new): `scripts/make_pulse_basal_probe.py` writes a probe recording to check
  both decodes in the real SpO2 Assistant.

---

## Findings T1-T8 (hardware investigation log)

Found while building the simulated-hardware tests (`tests/hwsim.py`,
`tests/test_hwsim_linux.py`, `tests/test_hwsim_realtrace.py`). Each is
pinned by an `expectedFailure` test that starts passing, and is reported as
an unexpected success, when the defect is fixed. T1-T5 were first
reproduced against the vendor-tool capture
`analysis/bum400_20260906_100516.pcap`; `tests/fixtures/cli-exchange.trace.json`
is the CLI's own traffic with the real device (Windows 8.1, hid backend,
214-sample session, recorded 2026-10-15) and confirms or extends them as
noted per row. T6 and T7 come from that recording.

**DONE (psytrap, 2026-10-15):** a real ~15.5 minute session (937 records,
session 3, recorded same day) settled this. `fiedle400 download` gave
937/937 records, 0 sequence gaps, matching the header exactly; the exported
CSV has 0 duplicate timestamps and a uniform 1.00s gap end to end across the
whole span -- no T6-style overlap or repetition anywhere, crossing roughly
4-5 window-boundary transitions (937 raw samples over a ~214-per-window
capacity). T6's fix holds on real multi-window data, not just the simulator.
Plotted and sent to psytrap for the G7 visual check alongside a second,
shorter real session (92 records) recorded the same day.

Still not settled by either recording: neither contains a finger-out moment
(both report `flags=ok` throughout), so T1's sentinel path (SpO2 127 / pulse
255) remains untested against real hardware -- synthetic frames only.

**Update (psytrap, 2026-10-15), unconfirmed:** deliberately pulled the probe
off mid-recording to test this. psytrap's hypothesis: the device's own
recording stops (rather than continuing and writing probe-out-flagged
samples) when the finger comes off. Not yet verified technically -- if true,
T1's sentinel path may be effectively unreachable via the storage path on
this firmware regardless of the decoder fix.

**Status: T1 to T7 are fixed in patch 0013** (the tests that pinned them now
assert the correct behaviour) and verified on the real device (Windows 8.1
laptop, `0.1.11`), not just the simulator: `sessions`/`download` show
107/107 records in 1m 47s with 0 sequence gaps (was 214 padded records,
4m 03s), `info` shows `Device Model Descriptor: 50F` and honest "not
reported by the device" for the rest, exactly as predicted before the run.
The Next step column keeps the original proposals; each row ends with what
was done. T8 (below) was found during that same verification pass -- the
fix itself is confirmed correct; T8 is a separate, pre-existing backend
quirk it happened to surface.

| # | Finding | Evidence | Next step |
|:--|:---|:---|:---|
| **T1 Status flags read from the MSB mask byte** | `engine/detector.py` takes `flags = chunk[7]` of every 30-byte `0xED` frame, but PROTOCOL.md 3.5 defines byte 7 as the third MSB mask (`m2`), not a status field. Whenever a data byte in positions 22..28 has bit 7 set (every `0xF_` baseline escape does), `m2` is non-zero and the frame is reported as `searching`/`low-perfusion`. `engine/device.py` then stores those samples as `None`. | In the capture the last frame of each page (seq 5, `m2` = `0x60`) decodes as `searching,low-perfusion`; a download keeps 103 of 122 records and blanks the last 19. The other frames decode as `ok`. | **Confirmed on the real device** (`test_the_last_frame_of_a_window_is_read_as_probe_out_today`, `test_no_samples_are_lost_at_the_end_of_a_window`): each reply ends with a short filler frame (seq 5, 8 raw values) whose mask bytes are `0x7f`; byte 7 = `0x7f` reads as `probe-out,searching,low-perfusion`, so its 4 averaged pairs are not decoded (103 of 107 per reply, no `None` samples because the frame is skipped, not blanked). The CLI's "103/214 records" at the halfway checkpoint is this plus T6. **Unblocked (psytrap, 2026-10-15): proceed, flagged for double-checking rather than gated.** Byte 7 is `m2` (§3.5), not a status field, and the storage stream's own documented finger-out signal is different: a sentinel in the decoded value itself (`analysis/bum400_20260906_100516.md` §4 -- SpO2 out of range -> `0x7F`/127, pulse out of range -> `0xFF`/255), not a flag byte. Stop deriving probe-out from byte 7 for `0xED` frames; use the documented sentinel values instead. Re-verify against the 5-10 minute recording (TODO above) once it exists, and against the real serial-stream devices if any are available -- this device only exercises the storage path. **FIXED in patch 0013:** Both frames and flags: `engine/detector.py` no longer takes status flags from byte 7 of `0xED` series frames; a reply's short final frame (ends with the `0xFF 0xFF` terminator) is decoded like any other; out-of-range values (SpO2 127, pulse 255) mark the second as a finger-out record (`flags` = `probe-out`, SpO2 and pulse empty). Legacy single-sample frames keep their flag handling. **Flagged for double-checking (psytrap):** re-verify against the 5-10 minute recording and a real serial-stream device. |
| **T2 Silent device counts as a successful download** | With every reply dropped, `download` prints "No active session table returned; defaulting to downloading Session #1", saves an empty file and exits 0. | `test_device_that_never_answers_is_not_reported_as_a_successful_download` | Exit non-zero (and write no file) when no session answered or zero records came back. **FIXED in patch 0013:** `download` prints "No recording data was received from the device, so nothing was saved" and exits 1 without writing a file. |
| **T3** ✅ **confirmed** -- Session length is shown about twice too long | The header count (243) is raw 2 Hz values (`analysis/bum400_20260906_100516.md` section 5: 243 values = 122 s) and an independent decompression gives 243 values per series. `SessionInfo` treats it as seconds, so `sessions` shows 4m 03s for a 122 s recording and the engine never reaches its record target (it asks for page 1 and retries). PROTOCOL.md 3.2 and 1 also said "seconds" -- that mislabel is now fixed. **Mechanism confirmed by psytrap (2026-10-15):** the device genuinely takes two independent raw half-second readings per second -- not duplicates -- and the firmware/decoder average them into one physiological 1 Hz value. That is why the raw header count is exactly double the real duration: it counts the two half-second readings separately, before they are merged. Not a decode bug, a label bug -- the merge-by-averaging the decoder already does (`detector.py`: `round((v1+v2)/2.0)`) is correct and matches `analysis/bum400_20260906_100516.md` section 5's own description of the firmware behaviour. | `test_header_count_is_in_raw_2hz_samples_so_duration_is_about_two_minutes` (pcap, 243 -> 122 s), `test_header_count_is_in_raw_2hz_samples_so_duration_is_107_seconds` (real, 214 -> 107 s) | Treat the header value as 2 Hz samples (duration = count // 2) in `SessionInfo`/the engine's record-count target. PROTOCOL.md §1 and §3.2 are fixed; §3.5.3 now states the confirmed merge mechanism. No decoder change needed -- the averaging was already correct, only the field's label and the duration/count math around it were wrong. **FIXED in patch 0013:** `parse_session_index_table` reads the 0xEC count as raw samples: `SessionInfo.raw_samples` = count, `record_count` = `duration_sec` = `(count + 1) // 2` (an odd count keeps its last reading: 243 -> 122, matching the 122 records decoded from the capture). Decoder unchanged. |
| **T4 `info` prints made-up values** | When the device does not answer, `command_info` still prints firmware "v2.0", serial "50F", user "user" and geometry "112 Bytes Sub-chunk Payload" from hard-coded fallbacks, indistinguishable from real readings. | `test_info_does_not_print_made_up_values_when_the_device_is_silent` | Print "not reported" instead of the fallbacks. **Real device:** it answers `0xAD` and `0x9E` with a bare `f0 70` ACK, so there is no firmware version, serial number or geometry to read; `info` shows hard-coded values for them. Worse, the `0xF1` reply to `0x81` is the hardware model descriptor (`50F`, PROTOCOL.md) and `parse_serial` prints it as "Serial Number" (`test_model_descriptor_is_not_labelled_serial_number`); the firmware line is the fallback `v2.0 (CMS-60D/PO-400 v2)` (`test_firmware_line_is_not_a_hard_coded_fallback`); the code ignores the `0xF1` reply because it checks `report[0] == 0x81`. PROTOCOL.md lists `80 00` -> `0xCF` as the firmware query, which the CLI never sends: `record_exchange.py --probe-firmware` records it. **FIXED in patch 0013:** `info` prints "not reported by the device" for firmware, serial, user profile and geometry when the device did not give them. The 0xF1 reply to `0x81` is shown as `Device Model Descriptor` (`50F`). (Correction to the first write-up: `parse_serial` was not involved; `50F` in the Serial Number line was the CLI's hard-coded fallback and only happened to equal the real descriptor.) The probe recording shows `80 00` is also answered with a bare ACK, so the device reports no firmware version at all. |
| **T5 Storage-frame checksum is never verified** | Every real `0xED` frame in the capture carries a correct 7-bit checksum, but the detector decodes frames with a wrong one. A corrupted frame silently yields wrong samples. | `test_frame_with_a_bad_checksum_is_rejected` | Drop (and count) frames whose checksum fails. Safe on the capture: all 12 frames pass. **FIXED in patch 0013:** The detector drops a series frame whose 7-bit checksum is wrong (event `CORRUPT_FRAME`); `download` then warns with the count. Samples after a dropped frame may be misaligned between the SpO2 and pulse series, so the warning tells the user to download again. |
| **T6 The page number is a sample offset, so downloads repeat the session** | A `9D 04` read's "page" argument is the offset, in raw samples, where the reply starts: offsets 0, 1, 2 return the same 214-sample session starting 0, 1, 2 samples in (214, 213, 212 values; reply k equals reply 0 from sample k, both series, verified). The engine treats it as the next page, so for a 107-record session (header 214) it asks for windows 0, 1 and 2 and exports 214 records: records 0..102 from window 0, 103..205 from window 1 (shifted by one raw sample, so the averaged pairs differ slightly), 206..213 from window 2. Anything after the first record is a repeat of the same minutes. | `test_download_today_returns_214_records_that_repeat_the_session_three_times_over` (characterisation), `test_each_sample_of_the_session_is_exported_once`, `test_the_page_number_is_a_sample_offset_each_reply_is_the_session_shifted_by_that_many_samples` | Unknown: what one reply holds at most (the recorded reply is the whole 214-sample session in 6 frames), the offset unit for longer sessions, and what the device sends past the end. Needs a longer recording and `record_exchange.py --probe-offsets` (read-only). Fix after T3: stop at the true record count and request the next window at offset = samples received. **FIXED in patch 0013:** The engine requests the next reply at offset `2 * records_so_far` (not page 1, 2, ...) and stops on a reply that adds no record. One reply covers the whole 214-sample session, so a download is now one window (7 commands plus ack). `tests/fixtures/probe.trace.json`: offset == stored samples gives an end marker, beyond it silence. **Confirmed on real multi-window data (psytrap, 2026-10-15):** a 937-record (~15.5 min) session downloaded as 937/937 records, 0 sequence gaps, 0 duplicate timestamps, uniform 1.00s spacing throughout -- across roughly 4-5 window-boundary transitions. |
| **T7 Storage geometry is the ACK byte** | The device answers `9E 40 04` with `f0 70`. `parse_storage_architecture_response` accepts `0xF0` and reads byte 1 (`0x70` = 112) as a chunk size, so `info` prints "112 Bytes Sub-chunk Payload", which is the ACK's status byte, not a geometry. | `test_geometry_is_not_derived_from_the_ack_byte` | Accept only `0x9E`/`0x9F`/`0xEF` replies; print "not reported" otherwise. **FIXED in patch 0013:** `parse_storage_architecture_response` accepts only `0x9E`/`0x9F` replies, no longer the `0xF0` ACK. |
| **T8 Linux `hid` backend's unlock/query gets no useful reply** *(open, found 2026-10-15, after patch 0013)* | On this Linux machine, `--backend hid` connects fine, but the unlock handshake and session-reset writes get **no reply at all** (not even an ACK), and the session query gets a bare ACK (`f0 70`) instead of `0xEC` data -- `sessions` then reports zero sessions. `--backend hidraw` on the *same device, same moment* works perfectly (107 records), and `--backend hid` on the real **Windows** laptop also worked perfectly with the identical Python-level code (G5/G6). So the shared code (`HidBackend`, the engine's command sequencing) is not at fault -- demonstrably fine on Windows. | Reproduced cold (not residual state from switching backends: a fresh 5s and a fresh 20s wait before trying `hid` alone both still fail the same way) and ruled out as a timing race (polled for a full 1s after the query write; the bare ACK arrives instantly, nothing ever upgrades to real data). The project's own `time.sleep()` values are deliberate, matched against the vendor pcap's timing, not the cause. **Likely needs a genuine USB re-enumeration (unplug/replug), not more elapsed time** -- untested, since that is not remotely automatable. | Open. Likely low real-world severity: the README documents Linux `hid` as the backend "for cross-platform testing on Linux", not the real Linux path (`hidraw` is, and is extensively verified); real Windows users get native `hid.dll`-backed hidapi (verified working); macOS would get `IOHIDManager`-backed hidapi, structurally closer to Windows's native path than to Linux's libusb path, though **this is unconfirmed -- no macOS hardware has been tested.** Candidate causes, none yet checked: the `0x00` report-ID prepend framing interacting badly with libusb specifically, a libusb transfer-type quirk, or the kernel-driver-detach dance (`wait_for_hidraw_reattach`, commit `69bb1bb`) leaving the device in a state only a real re-enumeration clears. `fiedle400 -b hid selftest` reproduces it in two lines instead of a manual trace (correction 2026-10-16: up to 0.3.6 the backend flag had to go before the command, because `selftest` did not accept it; since 0.3.7 `fiedle400 selftest -b hid` works too, and `--backend` is the long form in both places). **Re-confirmed still open (2026-10-15, after v0.2.17):** `fiedle400 -b hid selftest` on this machine: Handshake+info and RTC read both still fail ("no data returned"); Session index now reports "0 session(s)" -- consistent with the device genuinely holding zero sessions right now (confirmed separately via the working `hidraw` backend), but this run alone can't distinguish a real `0xEC` reply from a silently-defaulted zero, so it is not read as a sign of improvement. |

---

## Manual-mode protocol: discovery and resolution (2026-10-15)

**Separate observation, corrected (psytrap, 2026-10-15):** `sessions` went
from 3 visible, to 1, to 0, over the course of this testing. The first
hypothesis here was that this was only a query/indexing mismatch -- Auto vs
Manual recording mode -- with the data still intact on the device. **Status
uncertain, not contradicted:** after an explicit Record on-then-off cycle,
the device's own display shows **no session-count indicator at all** --
not an explicit "0". Ambiguous: this could mean zero sessions (some UIs
only show a count when there is something to count), or that psytrap was
not on the screen that would show one. Not yet resolved either way.

**Mechanism for sessions 1-3's disappearance, confirmed (psytrap):** switching
the device from Auto to Manual recording mode erases its memory. That fully
explains the 3 -> 1 -> 0 sequence; not a protocol or query bug.

**User-slot hypothesis, tested and ruled out:** `PROTOCOL.md` 3.13 documents
per-user erase for slots 1-6 (`0x91`..`0x96`), while the implemented
`QUERY_SESSIONS`/`SESSION_RESET` commands (`commands.py`
`build_session_index_query_command`/`build_reset_session_index_command`) take
no user parameter at all -- hardcoded to slot 1. Tested directly on hardware
whether byte `[1]` doubles as a user selector there too, mirroring the erase
command's framing: queried slots 1 through 6 explicitly after a fresh Manual-
mode recording. **All six returned the identical bare `COMMAND_ACK`, not
`0xEC` data for any slot.** This rules out "stored under a different user
slot, unreachable by our hardcoded query" -- if that were true, at least one
slot should have answered with real data. The simpler explanation now looks
more likely: the Manual on-then-off cycle did not actually commit an indexed
session at all, for a reason not yet found (missing a save/confirm step on
the device? a minimum-duration threshold?) -- not a protocol addressing gap
in this tool. Still needs confirming directly on the device's own UI.

**Independent confirmation found in the vendor's own software (psytrap, found
via static analysis of `archive/bruteforce/SpO2.exe`, not git-tracked --
`.gitignore`d, a pre-existing local artifact from the original protocol
reverse-engineering, same method `PROTOCOL.md`'s own header credits):** its
UTF-16LE strings include the literal confirmation-dialog text *"Changing the
storage mode will erase the stored data in the device. Are you sure you want
to do this?"*, plus internal names `STR_StorageAuto`, `STR_StorageManual`,
`STR_ChangeStorageModelNote`, `bAutoDeleteSegmentSaveData`,
`bManualDeleteSegmentSaveData`. "Storage Model" (Auto/Manual) is a real,
named, vendor-acknowledged concept with its own erase warning -- independent
confirmation of the mode-switch-erase finding above, not a misreading on our
side.

**`SESSION_SELECT`/`SESSION_DOWNLOAD` (`0xA5`/`0xA6`) hypothesis, tested and
ruled out on real hardware:** `PROTOCOL.md` 3.12 already flags these as "used
on serial-stream device models" (this one is flash/storage-based, via
`0x9C`/`0x9D`), raising the question of whether Manual-mode sessions route
through that other addressing scheme instead. Tested directly: unlock,
flush, `reset_session_index`, flush, then `SESSION_SELECT`+`SESSION_DOWNLOAD`
for session IDs 1-3, each read immediately after. All six writes got **no
reply at all** -- not even a bare ACK. Sanity-checked on the same connection
immediately after: a raw `READ_RTC` (`0x82`) built the identical way got a
correct, well-formed reply, confirming the test method itself was sound. This
firmware does not answer `0xA5`/`0xA6`; ruled out, not a dead end from a
bug in the test.

A heuristic static scan of the vendor exe for undocumented command templates
(byte sequences matching this project's own `sum(bytes) % 128` checksum
convention) was tried and abandoned: a 3.3MB binary has enough coincidental
matches that it did not discriminate real command tables from random data
without much tighter constraints than attempted. Not pursued further -- the
remaining open question (how, or whether, a Manual-mode session can be read
via USB at all) is better answered by the device's own UI than more blind
byte-pattern guessing against an unfamiliar binary.

**RESOLVED (psytrap, 2026-10-15): Manual mode has its own, completely
separate protocol** -- `0xA0`/`0xD0` (header), `0xA2`/`0xD2` (pulse),
`0xA3`/`0xD3` (SpO2), `0xA7`/`0xD8` (block ack), found via a live USB capture
of SpO2 Assistant reading a real Manual recording, cross-referenced against
`SpO2.exe`'s disassembly. Full byte maps now in `PROTOCOL.md` §3.14 and
`analysis/po400_bytemap_reference.md`. This is why `0x9C`/`0x9D` (and the
ruled-out `0xA5`/`0xA6` hypothesis just above) never found anything: Manual
sessions were never reachable through the Auto-mode storage path at all, by
design, not by a bug. All the guessing above -- user slots, `0xA5`/`0xA6`,
the static byte-pattern scan -- correctly found nothing, because none of
those were the real mechanism.

Verified live against the real device, not just transcribed:
- `0xA0` header query: confirmed, but the original transcription had the
  date/time/duration fields one byte too early (missing an unidentified
  `0x00` byte at offset `0x01`); fixed in both docs.
- `0xA3`/`0xD3` and `0xA2`/`0xD2` data blocks: **framing confirmed, value
  decode formula not yet correct.** 3 reports, 7 subframes each, every
  subframe's checksum validates, and whole-`0x7F` sentinel subframes line up
  at the same positions in both streams (seq 0, 2, 5) -- strong evidence the
  two series are measured together, second by second. But decoding the
  non-sentinel bytes with the documented fixed-base-per-subframe formula
  gives overlapping, physiologically impossible values for both series
  (negative numbers, values over 127). Likely needs a running baseline
  (analogous to the storage path's own dynamic-baseline escape, §3.5.3)
  rather than one fixed value per subframe -- not yet tested.
- Device behaviour, independently clarified: Manual mode holds exactly **one**
  recording slot, overwritten every time a new Manual recording starts
  (psytrap, confirmed via the device's own on-screen warning). This explains
  both the mode-switch erasure (Auto and Manual use entirely separate storage)
  and why the queried duration (41 s) need not match any particular earlier
  recording attempt -- it reflects whatever is in that one slot right now.

Not yet done at this point: the running-baseline hypothesis, and any actual
code implementation (`fiedle400` had zero support for these opcodes --
protocol knowledge, not a working decoder). Also unexplained: why SpO2
Assistant itself did not detect the device during this session (Windows-level
connect sound heard, device not shown in the app) despite having worked
before -- not reproduced further once the Manual-mode protocol investigation
took priority; the USBPcap/Wireshark capture tooling installed for this
(`enable_testsigning`, TESTSIGNING now on) remains unused for that specific
question and sits on the laptop for whenever it is revisited.

**RESOLVED: the Manual-mode delta decode is solved and verified (psytrap,
2026-10-15).** The base value sits at record offset `0x05`, not `0x03`. Two
earlier attempts read it from `0x03`, which inflated SpO2 to 116-127 and
produced negative Pulse values; that single off-by-two is what generated
both the bogus "subtract a constant 27-28" hypothesis and the bogus
"ramp-up transient" reading of subframes 1 and 3. Neither was real. With the
base at `0x05`, a running chain `S_n = S_(n-1) +/- magnitude` over
high-nibble-first sign/magnitude deltas from `0x06`, a shared `0x7F`
sentinel, byte-level `0x7F` padding and a nibble-level `0xF` end marker, all
8 data subframes decode to textbook values with no correction of any kind:
SpO2 96-100%, Pulse 62-67 bpm, 59 samples with signal over a ~140-sample
timeline, three no-finger gaps. Full spec and reference implementation in
PROTOCOL.md §3.14.F; German mirror in `analysis/po400_bytemap_reference.md`.
Notably the relayed disassembly note ("byte `0x04` of the data region is the
base") was **correct all along** -- counting the data region from the `seq`
byte, index 4 is `rec[5]`. The error was local, not in the relayed findings.

**Static disassembly of the local `SpO2.exe` is a confirmed dead end -- stop
trying.** Three methodologically independent scans agree this build does not
contain the Manual-mode decoder: alignment-independent raw byte-pattern
cluster search (shift-by-4 near a `0x0F`/`0x07` mask near a sign test, zero
hits), signed 4-bit lookup-table search across `.text`/`.rdata`/`.data`
(zero hits), and inspection of all 22 `[reg+5]`/`[reg+6]` load pairs (the
only promising one is DES in a crypto library at `0x42e2xx`). psytrap
confirmed the relayed disassembly came from a third installation, different
from both this archived copy and the laptop's V3.0.5. An earlier linear
capstone sweep that "found" clusters was desynced and its results are
void -- it reported 5 `and reg,7` in 1.7 MB where a raw scan finds 29. The
method notes, section table, useful byte encodings and known decoys are now
written up in PROTOCOL.md §3.15 so this is not re-attempted from scratch.

**RESOLVED: opcode `0xA4` is not a Manual-mode mystery -- it's an existing
Auto-mode opcode (live-checked against source, 2026-10-15).**
`fiedle400/protocol/models.py` already defines `0xA5` ("select active
session index slot") and `0xA6` ("initiate session download handshake") in
the same family as `0xA2` (`STORAGE_NEGOTIATION`), all part of the
already-implemented Auto-mode storage protocol. The disassembly whitelist
cluster that grouped `0xA2/0xA3/0xA4/0xA5/0xA6` together is that same
Auto-mode session-selection family, not a Manual-only opcode. A second
relayed disassembly pass (2026-10-15) gives it a specific role, not yet
re-verified against this project's own binary: `SEGMENT_QUERY` /
`SEGMENT_PREPARE`, sent once per stored segment in a loop
(`for i in 0..TotalSegments-1`) immediately before `0xA5`
(`SESSION_SELECT`) -- i.e. it walks the device's segment list to position
the read pointer before a specific session is selected. Plausible and
consistent with the A2/A5/A6 family it was already placed in; not pinned
down by direct testing here.

**Partially resolved: the duration-field discrepancy is real and
reproducible, not a one-off.** Re-pulled the exact same stored recording
live from the device (2026-10-15): byte-identical to the earlier capture,
confirming it is deterministic, not a transcription artifact. Header still
says 41 s. Subframe `seq=3` alone decodes to 27 samples with **no
terminator at all** -- it simply runs out of its 13 delta bytes without
ever hitting a `0x7F` byte or `0xF` nibble -- and the four non-"no-finger"
subframes total 59 real samples by themselves, already past 41. If each of
the 7 subframes instead represents a fixed ~5.86 s reporting window
(41 / 7) regardless of how many internal delta-samples it carries, the
totals reconcile, implying the device samples faster than 1 Hz internally
and the per-nibble index is not directly seconds. A second relayed
disassembly pass (2026-10-15) offers a specific mechanism for this: the
device's own reader (claimed at `0x00479fc5`, unverified build) allegedly
stops consuming samples once a running count reaches the header's duration
value, treating everything past that point -- even same-value deltas
indistinguishable from genuine flat readings -- as discardable block
padding. Credible, not independently checkable from raw bytes (that is
exactly the `0x00`-delta-vs-padding ambiguity already on this list).
Resolving it for real still needs a **precisely timed** fresh Manual
recording (e.g. exactly 20 s by stopwatch, started and stopped on the
device itself) compared against the resulting header duration and
decoded sample count -- a physical button-press on the device, not
something done from here. (This question is still open as of the move to
this changelog; see `RELEASE_PLAN.md`'s current open-findings section.)

**RESOLVED (two independent methods agree): high-nibble-first.** The
empirical smoothness check on this capture was a near-exact tie (23 vs 24
out of 189 points) and could not settle it alone. A second, independently
relayed disassembly description of the decode loop matches this project's
nibble math exactly (sign at bit 7 of the byte, magnitude in bits 6-4 for
the first sample; sign at bit 3, magnitude in bits 2-0 for the second) --
corroboration, not the origin, of what PROTOCOL.md §3.14.F already
specifies. Treat as settled unless a sharp-transition capture disagrees.

**Found and flagged, not resolved: the relayed claim about offsets
`0x03/0x04` does not match the live data.** The same disassembly pass
claimed `rec[0x04]` in this document's indexing (its own indexing counts
from the `seq` byte) is a constant hardware channel-ID byte, `0x08` for
SpO2 and `0x04` for Pulse. Checked directly against the live capture: it
is not constant -- `0x7C, 0x00, 0x7F, 0x7F` across SpO2's four real
subframes, `0x7D, 0x00, 0x7F, 0x7F` across Pulse's. Still unidentified;
specifically not a fixed per-series tag as claimed. A relayed claim that
contradicts a direct live measurement loses to the measurement. (Still
open; see `RELEASE_PLAN.md`.)

**Also found and fixed in PROTOCOL.md's prose:** `build_hid_command` in
`fiedle400/protocol/commands.py` pads unused report bytes with `0x80`, not
`0x00` -- a raw test write using `0x00` padding got no response from the
real device at all. And `UNLOCK_HANDSHAKE` + the `0xA2` negotiation half
are sent as **one** concatenated 64-byte write
(`build_unlock_negotiate_handshake`), not two separate 64-byte writes --
§3.1's two-table layout used to read as if they are separate transmissions,
fixed. Live reproduced: the correct combined/padded framing works
immediately; the naive two-writes/0x00-padding framing gets silence.

Implementing the decoder in `fiedle400` is cloud's side of the split -- the
protocol side is documented and ready.

> [!NOTE]
> **Superseded paragraph, kept for the record.** The following was written
> *before* the "Manual mode has its own, completely separate protocol"
> finding above, during an earlier dead end, and is contradicted by it --
> Manual mode's Auto/Manual question was resolved, not left open. Kept
> verbatim rather than deleted, since it documents a real (if ultimately
> wrong) investigative step: "Raw trace of the session query after that
> cycle: a bare `COMMAND_ACK` (`f0 70`), no `0xEC` data -- the same shape as
> T7's bare-ACK pattern on other queries, now also seen on the
> session-index query itself. psytrap: 'storage concept must be different'
> -- i.e. our model of how this firmware creates and retains a session
> (PROTOCOL.md's `MAX_SESSION_SLOTS` picture) may not match how sessions
> 1-3 actually got created. Next step: establish exactly what sequence
> produced sessions 1-3 in the first place, and try to reproduce it --
> guessing at menu modes without that is not converging. Still blocks: T1's
> real finger-out test, and the Auto/Manual question itself (open again,
> not resolved either way)."

---

## Gate re-verification log (G5/G6, real hardware)

Full history of G5/G6 hardware re-checks on both platforms, moved here to
keep `RELEASE_PLAN.md`'s gate table current-state-only (2026-10-16).

**`0.3.7` (psytrap, 2026-10-16), docs-review patch (0015):** Linux (`.venv`,
`hidraw`): `info`/`sessions` correct against the real device. Windows 8.1
laptop (reached over SSH): PyInstaller for `py -3.8`, `dist\fiedle400.exe
info`/`sessions` both correct (`hid` backend; clock honestly "not reported
by the device"). Windows installer/`.iss` not exercised, only the raw
PyInstaller build -- fine for G5's purpose. `FIEDLE400_LIVE=1` suite: Linux
7/7 pass (clock bytes match the patch's prediction exactly); Windows 5/5
applicable pass, 2 correctly skipped as Linux-only.

**`0.3.8` (psytrap, 2026-10-16), wizard/udev/desktop-launcher patch:** Linux
rebuilt (43MB -- matplotlib now actually bundled; the `0.3.7`-era Linux
builds that session were accidentally built from a `.venv` without
matplotlib installed, so `plot` silently degraded, fixed here), `info`/
`sessions` correct, `FIEDLE400_LIVE=1` suite 7/7 pass. Windows: repo
re-synced to the laptop (it was stale at `0.1.10`), rebuilt, `info` correct,
`FIEDLE400_LIVE=1` suite 5/5 applicable pass.

**`0.3.9` (psytrap, 2026-10-16), `selftest` multi-backend probe:** Linux:
rebuilt, `info`/`selftest` both correct -- `selftest`'s new automatic
both-backend probe showed `hidraw` and (this run) `hid` both passing
cleanly, after T8 had reproduced on `hid` moments earlier following a
device unplug/replug (see RELEASE_PLAN.md T8). `FIEDLE400_LIVE=1` suite
7/7 pass. Windows: re-synced, rebuilt, `info`/`selftest` correct,
`FIEDLE400_LIVE=1` suite 5/5 applicable pass.
