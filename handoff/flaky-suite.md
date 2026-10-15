# Delegation brief: intermittent full-suite failure

Written by the local session for the cloud. The cloud has read-only access to
this folder; the USB device exists ONLY on the local machine, so all hardware
evidence below was gathered locally and cannot be reproduced in the cloud.

## Task

Diagnose the intermittent failure described below and, if the cause is in
product/test code, deliver a fix as the next numbered patch. If the cause is
hardware-layer, say so and the local side will fix it.

## Symptom

    cd /home/mik/Documents/Bastel/2023-/po400
    python3 -m unittest discover -s tests -t .

One run reported `FAILED (failures=1)`. The 10 immediately following runs all
reported `OK`. Roughly 1 failure in ~14 observed full-suite runs.

IMPORTANT: the identity of the failing test was NOT captured before it stopped
reproducing. It was a *failure* (assertion), not an *error* (exception). Do not
assume which test it was; the local side can re-run to capture it on request.

## Second anomaly, possibly the same cause

Reported skip counts vary run to run under the same interpreter:

| interpreter | before patch 0002 | after patch 0002 |
|---|---|---|
| system python3 (has matplotlib, hid) | OK (skipped=1) | OK (skipped=6), and a later run with no skips at all |
| .venv/bin/python (no matplotlib)     | OK (skipped=6) | OK (skipped=5) |

6 is exactly the number of tests in tests/test_device_live.py.

Hypothesis worth checking in code: test_device_live.py guards its class with
`@unittest.skipUnless(is_device_connected(), ...)`. A decorator argument is
evaluated at MODULE IMPORT time, and `unittest discover` imports every test
module up front. So all 6 hardware tests are included-or-skipped based on device
state at import, not at run time. Anything perturbing the device around import
flips all 6 at once.

## Hardware facts the cloud cannot observe

- Device: Pulsox PO-400, VID 28e9 PID 028a, currently /dev/hidraw10.
- The installed `hid` module is cython-hidapi built against **libusb**, not
  hidraw. `hid.enumerate()` returns a bus path (`1-7.4.4:1.0`), not /dev/hidraw*.
- VERIFIED LOCALLY: when that libusb handle is open it detaches the kernel
  usbhid driver, and /dev/hidraw* **disappears entirely** for the duration,
  reappearing ~20-50ms after close once udev re-applies its rules. Measured:

      before:     /dev/hidraw10 mode=0o666 w_ok=True
      while-open: /dev/hidraw10 ABSENT
      t+50ms:     /dev/hidraw10 mode=0o666 w_ok=True

- This already caused one bug, already fixed locally in commit 69bb1bb:
  tests 04-06 of test_device_live.py ran inside that re-attach window and failed
  with a misleading PermissionError. Fix was `wait_for_hidraw_reattach()` called
  from test_03's finally block. The hardware suite alone is stable: 6/6 passing
  repeatedly.
- Two udev rules are installed locally: 99-pulsox.rules (hidraw) and
  99-pulsox-usb.rules (usb, needed by the libusb backend).

## Repo state

HEAD = 94eb354. Patches 0002 and 0003 are APPLIED but UNCOMMITTED:

    M .github/workflows/build-release.yml
    M README.md
    M RELEASE_PLAN.md
    M tests/test_export_spo2.py
    M tests/test_pcap_decoder.py
    ?? .github/workflows/tests.yml
    ?? tests/capture_tools/

The flake appeared immediately after 0002, which is therefore a prime suspect.
0002 newly made two previously-skipped tests execute for real: test_pcap_decoder
and the round-trip test in test_export_spo2 now import decoders from the new
tests/capture_tools/ and read analysis/bum400_20260906_100516.pcap. It also
changed an assertion in test_pcap_decoder.py from `len(sessions) == 2` to `== 1`.
Whether 0002 introduced the flake or merely exposed something pre-existing is an
open question.

Also worth checking: do tests/test_hid_driver.py and tests/test_serial_engine.py
touch real hardware, or only mocks?

## What the local side can run on request

Any experiment against the real device: looped suites, single modules, varied
run order, both interpreters, instrumented runs, timing measurements around the
hidraw node. Ask for specific commands and the output will be returned.

Constraint: never `po400 clear` or anything that erases device flash — the
stored sessions are real data. Read-only device operations only.
