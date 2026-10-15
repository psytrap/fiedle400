# Delegation brief: CI tests against mock hardware (Linux + Windows)

Written by the local side for the cloud, 2026-10-15, against HEAD `f5b17e6`
(version `0.1.4`). Task set by psytrap.

## Goal

Exercise the device-dependent code paths in CI across platforms, using simulated
hardware, so the parts that today only run when a PO-400 is physically attached
get covered on every push.

## What is and is not covered today

Covered by CI (163 tests, 7 skipped, ubuntu/windows/macos at Python 3.11):

- Protocol encode/decode, the packet engine, export, plotting, config, version.
- `MockHidDevice` in `fiedle400/hid_driver.py` already exists and is used by
  `tests/test_hid_driver.py`, `tests/test_serial_engine.py` and
  `fiedle400/engine/device.py`. It is a plain Python object with a canned
  response list -- it substitutes for the device *object*, not for the device.

Not covered anywhere except on psytrap's desk:

- `LinuxHidrawBackend` -- opening a real `/dev/hidraw` node, non-blocking reads,
  timeouts, partial reads, the `O_NONBLOCK` path.
- `find_pulsox_hid_devices()` -- the sysfs scan, VID/PID matching, the
  readability check.
- The full session flow end to end: connect → unlock handshake → session index
  → block download → non-destructive ack → export.
- Error paths: device disappearing mid-download, a truncated response, a bad
  checksum, a timeout.

The 7 skipped tests are `tests/test_device_live.py`, which is correctly gated
behind `FIEDLE400_LIVE=1` and needs the real device.

## Two approaches; the cloud should pick and say why

**A. Extend the existing `MockHidDevice` into a protocol-aware fake.**
Instead of popping canned bytes, it would parse the `0x7D 0x81` command frames
and reply as the firmware does: ACK to the handshake, `0xEC` session metadata,
`0xED` sample sub-chunks with correct 7-bit checksums and bitmask unpacking, an
`0xF2` RTC reply. `analysis/bum400_20260906_100516.pcap` and the byte-level
notes in `PROTOCOL.md` and `analysis/po400_bytemap_reference.md` are the
reference for exact framing -- the capture is already a tracked fixture and
`tests/capture_tools/decode_pcap.py` can replay it.

Cheap, portable (runs on all three CI platforms), no privileges. Does not
exercise the kernel path or the hidraw backend at all.

**B. A virtual HID device via the Linux `uhid` interface.**
`/dev/uhid` lets userspace create a HID device that the kernel then exposes as
a real `/dev/hidrawN`. A small helper could present VID `0x28E9` PID `0x028A`
and answer the protocol, which would exercise `find_pulsox_hid_devices()` and
`LinuxHidrawBackend` for real -- the code that today has no automated coverage.

Linux-only, and needs checking on a GitHub `ubuntu-latest` runner: whether
`/dev/uhid` exists or `modprobe uhid` is permitted, and whether the created node
is readable without a udev rule. **Verify that on a runner before building
anything on it** -- if it does not work there, B is dead and A is the answer.

A reasonable outcome is A now and B later, or A everywhere plus B as a
Linux-only job allowed to be skipped when `/dev/uhid` is unavailable.

## Windows needs this too (psytrap, 2026-10-15)

Scope this for Windows as well, not Linux only. Two things already true, so
they are not the gap:

- The full mock suite (163 tests) already runs on `windows-latest` via
  `tests.yml` -- nothing here is Linux-gated at the CI-matrix level.
- `tests/test_hid_driver.py` already mocks `HidBackend` -- the class Windows
  (and macOS) actually use -- at the wire level: `hid.enumerate()` parsing,
  `hid.device`/`hid.Device` style construction, the `0x00` report-ID prepend
  on writes, read/close. That is solid and does not need redoing.

The actual gap on Windows is the same as on Linux, one layer up: nothing drives
the *full protocol* (unlock handshake -> session index -> block download ->
non-destructive ack -> export) through an actual backend instance. Today only
`MockHidDevice` exercises that flow, and it bypasses `HidBackend` and
`LinuxHidrawBackend` entirely -- the engine talks straight to a Python object
with a canned response list, never through either backend's `write_report` /
`read_report`.

So whichever protocol-aware fake Approach A produces, it should be exercised
through **both** backend classes, not just injected into the engine directly:
a fake `hid` module (same `MagicMock`/`patch.dict(sys.modules, ...)` style
already used in `test_hid_driver.py`) that speaks real protocol bytes back
through `HidBackend`, and the existing hidraw-based approach (A or B) through
`LinuxHidrawBackend` on Linux.

**Approach B has no Windows equivalent.** `/dev/uhid` is a Linux kernel
interface; there is nothing comparable on Windows without a kernel-mode driver
or a signed virtual HID framework (e.g. HidGuardian or a custom KMDF driver),
which is almost certainly not worth building for this project. For Windows,
Approach A (a fake `hid` module speaking protocol) is the only realistic path
-- there is no B to fall back to there.

## Constraints

- Keep the real-hardware tests as they are: `FIEDLE400_LIVE=1`, device detection
  in `setUpClass`, the `flock` serialisation. Mock tests must run by default and
  must never need the gate.
- No prompting and no hangs: the suite must stay non-interactive. `config.py`'s
  `isatty()` guard and its tests exist precisely for that.
- Never make the mock so permissive that it passes where the real device would
  fail. A fake that always ACKs would hide exactly the bugs this is meant to
  catch. Prefer asserting on the bytes the code *sends*, not only on what it
  does with the replies.
- Patch-bump freely (RELEASE_PLAN §1, psytrap 2026-10-15).

## Worth knowing

Two real bugs this session were invisible to the current mocks, and are a good
yardstick for whether the new coverage is worth anything:

1. The frozen binary imported `hid` but could not call into it, reporting
   "no device found" on a machine where the device was plainly attached. Only a
   real install on real hardware caught it. A protocol-aware fake would not have
   caught this one either -- it is a packaging fault, worth noting so nobody
   claims the mock covers it.
2. `connect()` swallowed `hid.enumerate()` failures with `except Exception:
   pass`, so an installation fault looked identical to an absent device. A mock
   that can be told to *fail* would catch this class of thing; one that only
   succeeds would not.

Local side can run anything against the real device on request -- ask through
this directory. Never erase device flash: the stored session (214 records,
2026-09-30) is real data.
