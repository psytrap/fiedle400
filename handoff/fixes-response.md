# Response: fix order T3, T6, T1, T2, T4/T7, T5 (one patch)

Written by the cloud side, 2026-10-15, against HEAD `0a31b90` (version `0.1.7`). Answers `handoff/fix-order-approved.md`.
One patch, as asked. Suite: 252 run, 0 failures, 7 skipped (live), no expected failures left.
The version is not bumped (that is a release step).

## What changed in the product

| | Change |
|:--|:---|
| T3 | `0xEC` count is raw 2 Hz samples. `SessionInfo.raw_samples` = count, `record_count` = `duration_sec` = `(count + 1) // 2`. Your note said `count // 2`; the only difference is an odd count, which keeps its last reading (the capture has 243 raw values and 122 decoded records, not 121). |
| T6 | The engine asks for the next reply at offset `2 * records_so_far` instead of page 1, 2, ..., and stops on a reply that adds no record. On the real device a download is now one window: 8 commands, 107 records. |
| T1 | No status flags from byte 7 of series frames. A reply's short final frame (it ends with the `0xFF 0xFF` terminator) is decoded, so the last 4 pairs are no longer lost. Out-of-range values (SpO2 127, pulse 255) become a finger-out record: `flags` `probe-out`, SpO2 and pulse empty. Legacy single-sample frames keep their old handling. |
| T2 | `download` with no data received prints why and exits 1 without writing a file. |
| T4/T7 | `info` prints "not reported by the device" for firmware, serial, user profile and geometry when the device gave none. The `0xF1` reply to `0x81` is shown as `Device Model Descriptor` (`50F`). The geometry parser no longer accepts the `0xF0` ACK. |
| T5 | A series frame with a wrong 7-bit checksum is dropped (`CORRUPT_FRAME`), and `download` warns with the count and says to download again. |

Correction to my first write-up of T4: `parse_serial` did not print `50F` as the serial; that was the CLI's hard-coded fallback, which happens to equal the real model descriptor.

## What the probe showed (new facts, now in PROTOCOL.md)

- A reply at offset `k` always runs to the **end** of the stored data (214, 213, 212, 164, 107, 64, 1 values for 0, 1, 2, 50, 107, 150, 213), byte for byte equal to `window(0)[k:]`.
- Offset == stored samples (214) is answered with one frame of `0xFF` filler (an end marker that decodes to nothing); offsets beyond (215, 300) get no answer.
- `80 00` (firmware query) gets a bare ACK, like `0xAD` and `0x9E`: this device reports no firmware version.
- The probe file moved to `tests/fixtures/probe.trace.json` and a test uses it: a header announcing 400 samples ends at the marker instead of looping.

## What to double-check (as you asked for T1)

1. On the real device: `fiedle400 download` should give 107 records for the 214-sample session, no duplicated minutes, and `info` should show the model descriptor `50F` and "not reported" for the rest.
2. T1 relies on the documented finger-out values (127 / 255). Nothing recorded so far contains a finger-out period, so that path is tested with synthetic frames only. A short recording with the finger pulled out in the middle would settle it.
3. Still unknown: a session longer than one reply. The engine continues at `2 * records`, which is correct if the offset unit stays raw samples and a long reply is split into several; the 5 to 10 minute recording will show it.
4. T5 is conservative: one bad frame drops about 21 pairs and can leave SpO2 and pulse misaligned, hence the "download again" warning.

## Windows

Still theory, as agreed.

## Sync note

Rebuilt on `0a31b90` (your `HidBackend` fake-module tests). `tests/test_hwsim_hidbackend.py` mirrored the pinned defects, so it is updated the same way: its T1/T3/T4/T6/T7 tests now assert the correct behaviour through the `hid` transport as well.
