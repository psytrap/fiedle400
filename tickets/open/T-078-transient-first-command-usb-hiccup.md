# T-078: First command after idle occasionally fails to find/reach the device, succeeds on retry

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/hid_driver.py` (`find_pulsox_hid_devices`, connect path)
  - `tickets/done/2026-W43/T-052-findings-recheck-for-release.md` (T8 --
    the known, separate `hid`/libusb handshake issue; this looks like
    the same *class* of USB-settle flakiness but on a different code
    path, not T8 itself)

---

## Description & Context

During the `v0.4.41` release cycle's Ring 1 smoke test (2026-10-21),
running the just-built Linux binary against the real device:

```
$ ./fiedle400 info
Error connecting: No Pulsox PO-400 device found! Ensure USB cable is
plugged in and device is powered ON.
$ ./fiedle400 info      # immediately after, nothing else changed
[... succeeds normally, full device info printed ...]
```

`sessions` run in between (on the same binary, same device, same
session) connected fine on the first try. psytrap has seen this
"first command after some idle period fails, a retry right after
succeeds" pattern before -- not a one-off. Distinct from **T8** (the
`hid`/libusb backend's unlock handshake failing outright, needing a
real unplug/replug): this was the native `hidraw` backend, which is
supposed to be the reliable Linux path, and it was a plain "device not
found" on enumeration, not a handshake failure after connecting.

Not investigated further this cycle -- noted and deferred rather than
blocking the release, since a retry always seems to clear it.

## Criteria

- [ ] Reproduce deliberately (e.g. leave the device idle for N minutes,
      then run a command) to see if there's a predictable trigger
- [ ] Determine whether this is a kernel/udev enumeration race (sysfs
      not yet populated right after a power state change) vs. something
      `fiedle400` itself could retry internally
- [ ] If a clear, safe retry point exists, consider having
      `find_pulsox_hid_devices` (or the CLI's connect path) retry once
      automatically before giving up, instead of requiring the user to
      re-run the command
- [ ] Tests pass

## Execution Notes

(Not started.)
