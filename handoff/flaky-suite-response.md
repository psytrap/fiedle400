# Response: intermittent full-suite failure

Written by the cloud for the local side, answering `handoff/flaky-suite.md`. Ships with patch 0004.

## Findings (verified in the cloud)

- The mock suite is deterministic. With 0002 and 0003 applied, `python3 -m unittest discover -s tests -t .`
  passed 100 out of 100 runs, plus 20 more with the real `hid` module (hidapi) installed. Every run reported
  `OK (skipped=6)`. Nothing that 0002 added (`test_pcap_decoder`, the `test_export_spo2` round-trip) reads clocks,
  mtimes, randomness or the device.
- `test_hid_driver.py` and `test_serial_engine.py` are mocks only (patched `hid` in `sys.modules`, `MockHidDevice`).
  All `test_cli_*` tests patch `PulsoxHidDevice`. **Only `test_device_live.py` touches real hardware.**
- So the one failure was almost certainly one of the 6 live tests. A missed or slow device response surfaces as an
  assertion *failure*, not an error, which matches what you saw. Examples: `test_04` (`active_user_id != 1`, `rtc_time_str == "N/A"`),
  `test_05` (`rtc_dt is None`) and `test_01` (node not readable).
- Your skip-count hypothesis holds. `skipUnless(is_device_connected())` runs at import, so every run's skip count
  reflected the device state at that moment. Concrete reading of your table: system python's `skipped=6` after 0002 means
  the device was not seen at import in that run, and the later "no skips" run means it was. The mock-side skips
  (pcap before 0002, 5 plot tests in the venv) account for the rest exactly.

## Not yet known

- Which live test failed, and whether a second process (another run, or a local agent) held the device at the time.
  The cloud can't observe either.

## Patch 0004 (test code only)

1. Live tests are opt-in with `PO400_LIVE=1`. The default run is pure mocks, so its result and skip count no longer
   depend on the device. With `PO400_LIVE=1` and no device, the class fails loudly instead of skipping.
2. Device detection moved from import time to `setUpClass`, right before use.
3. A cross-process `flock` (`$TMPDIR/po400-live-tests.lock`, 120 s timeout) serialises live runs, so overlapping runs
   wait instead of colliding. Remove it if you'd rather own this in the hardware layer.
4. Assertion messages in `test_04` and `test_06` now include the device response, so the next failure names its cause.
5. `tests/test_live_harness.py` holds mock tests for the gate, the import-time behaviour and the lock.

## Requested local run (read-only on the device)

    for i in $(seq 1 30); do
      PO400_LIVE=1 python3 -m unittest tests.test_device_live -v > output/live_$i.log 2>&1 || echo "run $i FAILED"
    done
    grep -h -A12 "^FAIL:\|^ERROR:" output/live_*.log

If anything fails, the `FAIL:` block names the test and the device response. Send that back through `handoff/`.
