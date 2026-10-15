# Delegation brief: make the live test suite runnable on Windows

Written by the local side for the cloud. Neither side can run this: the cloud has
no device, and the local machine is Linux. The user has a **Windows 8.1** laptop
and will be the one executing the result, so the patch must be right by
construction and must fail loudly rather than silently skipping.

## Goal

`PO400_LIVE=1 python -m unittest tests.test_device_live -v` should give a
meaningful result on Windows, exercising the `hid` backend that Windows actually
uses, instead of failing on Linux-only assumptions.

## What breaks today, verified by reading the code

1. **`test_01_device_detection`** calls `find_pulsox_hid_devices()`, which scans
   Linux sysfs (`po400/hid_driver.py`, docstring says "via Linux sysfs"). On
   Windows it returns `[]`, so `assertTrue(len(devices) >= 1)` fails. The
   assertion `dev_path.startswith("/dev/hidraw")` is Linux-only by definition.
2. **`test_02_hidraw_backend_connection_and_descriptors`** constructs
   `PulsoxHidDevice(backend="hidraw")`. `po400/hid_driver.py` raises
   deliberately for that backend when `sys.platform` is not linux:
   "The 'hidraw' backend is only supported on Linux". So this test cannot pass
   on Windows and should not be made to.
3. **`wait_for_hidraw_reattach()`** is a Linux kernel-driver concept. There is no
   hidraw node on Windows, so the barrier in `test_03`'s finally block is
   meaningless there.

No change needed for the lock: `fcntl` is already import-guarded and
`_acquire_live_lock` returns `None` when it is absent, so it degrades to a no-op
on Windows rather than crashing. Confirmed by reading the code.

## What is wanted

- Platform-gate tests 01 and 02 as Linux-only, with an explicit skip reason
  naming the platform — not a silent pass.
- Add Windows equivalents giving the same coverage through the supported path:
  enumerate via `hid.enumerate(0x28E9, 0x028A)`, assert VID/PID and that a
  descriptor read succeeds, and exercise `PulsoxHidDevice(backend="hid")`.
- Make `wait_for_hidraw_reattach()` a no-op off Linux, keeping the assertion
  meaningful where it applies.
- Keep tests 04, 05 and 06 platform-neutral — they drive `SerialDeviceEngine`
  over whichever backend is default, which should already work on Windows.
- Preserve the rule that `PO400_LIVE=1` with no reachable device fails loudly.

## Target environment

- Windows 8.1, so Python 3.12 is the ceiling (3.13 requires Windows 10+).
  Recommend 3.11 to match the CI matrix exactly.
- The `hid` pip package needs `hidapi.dll` present on Windows; it does not
  install it. Worth a README line if the patch touches setup docs.
- Open question the laptop will answer: whether the PO-400 enumerates as a
  plain HID device or needs Zadig. See the TODO at PACKAGING.md:137. Do not
  assume either way.

## Constraints

- The user runs this on real hardware. Never erase device flash; stored sessions
  are real data. Read-only device operations only.
- Local repo state: HEAD 468ea4c, tree clean, nothing uncommitted.
