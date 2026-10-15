# Response: the real device trace

Written by the cloud side, 2026-10-15, against HEAD `490d4b6` (version `0.1.7`). Answers `handoff/trace-ready.md`.

## What changed

- The trace moved to `tests/fixtures/cli-exchange.trace.json` (it is test data now). It replays with **no unmatched command**:
  `tests/test_hwsim_realtrace.py` runs `sessions`, `download` and `info` against it on the real hidraw code path,
  with `FakeOximeter(strict=True)` (new): a request that was not recorded gets no answer instead of the last
  recording again.
- `record_exchange.py` gained two read-only probes, `--probe-firmware` (sends `80 00`) and `--probe-offsets N,N,...`
  (SpO2 reads at those sample offsets), see below.
- RELEASE_PLAN 3d: T1, T3, T4 extended with the real evidence; **T6** and **T7** added. No product code changed.
- Suite: 238 run, 0 failures, 7 skipped (live), 11 expected failures (the findings).

## About the "103/214" in the nudge

It is two findings together, and the first guess (T1 with T3) was half right:

1. 103 is T1: each reply ends with a short filler frame (8 raw values) whose mask bytes are `0x7f`. Byte 7 then reads as
   `probe-out,searching,low-perfusion`, so its 4 averaged pairs are skipped. 107 pairs arrive, 103 are decoded. On the
   vendor capture the same flaw *blanked* samples; here it *drops* them. T1 is confirmed on the real device.
2. 214 is T6, not a double count: the page number of a `9D 04` read is a **sample offset**. Offsets 0, 1, 2 return the
   same 214-sample session starting 0, 1, 2 samples in (214, 213, 212 values; exact match, both series). The CLI
   treats them as pages 0, 1, 2 and exports 103 + 103 + 8 records. The true session is 107 records. Records 103 onward
   repeat the same minutes.

(T3: the header's 214 is raw 2 Hz samples = 107 s, as you confirmed.)

## What `info` shows on this device

The firmware, serial and geometry queries (`0xAD`, `9E 40 04`) are answered with a bare ACK `f0 70`.
So `info` prints made-up or misread values: the firmware is the hard-coded `v2.0 (CMS-60D/PO-400 v2)`; "Serial Number 50F" is
the *hardware model descriptor* returned for `0x81` (an `0xF1` report; the code checks for `0x81` and so ignores it,
then `parse_serial` takes it as the serial); "112 Bytes Sub-chunk Payload" is the ACK status byte `0x70` (T7).

## What the trace cannot tell yet (please run once, read-only)

1. Sessions longer than one reply: what offset unit does the device use, and what comes after the end of the data?
2. Does `80 00` return the firmware version (`0xCF`)?

```bash
python3 tests/capture_tools/record_exchange.py --no-download --probe-firmware \
  --probe-offsets 0,1,2,50,107,150,213,214,215,300 -o handoff/probe.trace.json
```

Offsets past the end of the 214-sample session show the end-of-data behaviour (silence, a short reply, a marker). If you can
also record a session of a few minutes (say 5 to 10), run the same command with the default `download`
to see how one reply is split for long sessions. Measurements are in the file, as before.

## Fix order I would suggest (nothing changed yet)

T3 (`count // 2`, confirmed) then T6 (needs the probe above), then T1 (needs your decision, as agreed), T2, T4/T7, T5.
Fixing T3 alone sets the engine's target to 107 records: window 0 gives 103, so the last 4 would come from window 1 (shifted by
one raw sample, so slightly different values). That is why T1 should follow right behind it.

## Open question

Windows: should `HidBackend` get the same treatment (fake `hid` module, runs on every OS in CI), or stay a theory for now? Default: theory only.
