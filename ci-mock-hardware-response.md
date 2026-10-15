# Response: CI tests against mock hardware (Linux done, Windows as theory)

Written by the cloud side, 2026-10-15, against HEAD `2384f34` (version `0.1.4`).
Scope set by psytrap: finish the Linux simulation; for Windows, only a theory.

## What exists now

Approach A **and** B in one: a protocol-aware fake behind the *real* hidraw code, without
needing `/dev/uhid`.

- `tests/hwsim.py`
  - `FakeOximeter` replays recorded device bytes. It never invents a reply: a command with no
    recording is logged in `unmatched` and gets silence (so the code sees a timeout, as with a
    real device that ignores it). Every host report is kept in `sent`, so tests assert on the bytes
    the code *sends*. Destructive opcodes (`0xAA/AB/AC`, `0x91..0x96`, any `0x94` other than the
    `94 14` query) are refused and logged in `destructive`.
  - `HidrawSim` runs the real `LinuxHidrawBackend` against a fake `/sys/class/hidraw` + `/dev` tree
    and a `SOCK_SEQPACKET` socket behind the file descriptor (message boundaries, `EAGAIN` when
    empty, `ENODEV` after `unplug()`). Replies are queued inside `os.write`, so runs are
    deterministic; `VirtualClock` makes the engine's 250 ms quiet periods free (whole file: 0.14 s).
  - Matching is by meaning, not framing: the vendor tool's `9c 01 1d` and the CLI's
    `7d 81 9c 01 1d 80...` are the same command. Host checksums are **not** validated: the CLI's
    `9C 80 00` reset lacks the `1C` the spec lists and works on hardware, so the device's rule is unknown.
- `tests/test_hwsim_linux.py`: 49 tests, 5 of them expected failures (the findings below). The hidraw tests skip off Linux.
  Covered: sysfs scan (present, absent, other HID device, unreadable node), open flags
  (`O_RDWR|O_NONBLOCK`), report boundaries, unplug, `sessions`, `download` end to end (exact command
  sequence and bytes, retries, final non-destructive ack, no destructive command, decoded values
  cross-checked against the independent `decode_ed_subframes`, export to csv and `.spo2`), `info`,
  and the CLI under faults (unplug mid-download, no device, dropped frame, silent device).
- `tests/capture_tools/record_exchange.py`: records the CLI's own traffic from a real device
  (read-only; it refuses destructive commands before writing them) into a trace the simulator replays.
  Its own test runs it against the simulator and replays the result.
- Product change: `hid_driver.py` now reads `SYSFS_HIDRAW_ROOT` / `DEV_ROOT` module constants instead of
  literals, so the scan can be pointed at a fake tree. No behaviour change.

I checked the tests catch real regressions: removing `O_NONBLOCK`, making the final ack an erase,
and fixing T1 / T5 each flip the expected tests.

## What the simulation cannot do (and what closes the gap)

The only recording is the vendor tool's capture, which has: the session header, **page 0** of both
series of session 1, RTC, user name, live stream. It does **not** have the replies to the CLI's
`0xAD`, `0x9E 40 04` and `9C 80 00` queries, or page 1 onwards. Those get silence in the simulator, and
tests that depend on them assert exactly that (`unmatched` is pinned), so the gap cannot grow unnoticed.

**Please run on the real device (read-only), then drop the file into `handoff/`:**

```bash
python3 tests/capture_tools/record_exchange.py -o handoff/cli-exchange.trace.json
```

It runs the same calls as `info`, `sessions` and `download`, ending with the usual non-destructive
ack. The file contains the recorded measurements (the 214-record session) and device identifiers; use
`--no-download` for a file without measurements. With it I can make the simulator answer the CLI's
own commands (firmware, serial, geometry, every page) and tighten the `info` and multi-page tests.
Two things no capture shows yet: how the device marks the *last* session in `0xEC` (the code stops on
flag bit `0x40`; PROTOCOL.md calls that bit "data ready") and what a second session looks like.

## Findings (RELEASE_PLAN.md 3d, each pinned by an expected-failure test)

T1 status flags read from the MSB mask byte (last 19 of 122 samples blanked in the capture),
T2 a silent device is reported as a successful, empty download, T3 session length shown about twice
too long (header counts 2 Hz samples), T4 `info` prints hard-coded firmware/serial when the device is
silent, T5 storage-frame checksum never verified. None is changed here. T1 is the one that may
already show in real downloads: please look for `None` / blank samples at the end of each page in a
real `download --dump` result.

## Windows: theory only (nothing run, nothing assumed true)

The pure-Python parts above (fake, trace, `command_key`) already run on `windows-latest` in the normal
suite; the hidraw parts skip there. A fake `hid` module in front of `HidBackend` would run on Linux,
Windows and macOS CI and prove the *code's* behaviour. It cannot prove how Windows' HID stack behaves.
Hypotheses about that, each with a prediction and a read-only way to settle it on the 8.1 laptop:

| # | Hypothesis | Basis | Prediction | How to check |
|:--|:---|:---|:---|:---|
| W1 | Writes work because every CLI report is 64 bytes starting with a non-zero opcode, so `HidBackend` always prepends the `0x00` report ID. A command starting with `0x00` would be sent unprefixed and shift by one byte. | `hid_driver.py` `write_report` (`len == 64 and [0] != 0`) | Holds today (`info`/`sessions` work on the laptop). No current builder starts with `0x00`. | Mock test with a fake `hid` module: every `Commands.*` report reaches `write()` as 65 bytes with a leading zero. |
| W2 | `hid.enumerate(0x28E9, 0x028A)` returns exactly one entry. If Windows split the device into several top-level collections, `matched_list[0]` could be the wrong one. | `HidBackend.connect` takes the first match | One entry (it works). | `python -c "import hid; [print(d) for d in hid.enumerate(0x28e9, 0x028a)]"`: count entries, check `usage_page`, `usage`, `interface_number`. |
| W3 | The 15.6 ms `time.sleep` granularity does not hurt: polling drops from ~200 to ~64 reads/s, but the capture's live stream is about 19 reports/s (210 reports in 11.0 s, median gap 50 ms), so nothing overflows. `download` waits are all quiet-period timeouts, so it only gets a little slower. | pcap timestamps; engine's `_sleep(0.005)` loops | `detect` for 30 s reports ~570 stream reports on Windows, the same as Linux. A big shortfall would disprove it. | Run `fiedle400 detect` for 30 s on both machines and compare the packet counts. |
| W4 | Two different PyPI packages install a module called `hid` (`hid`, a ctypes wrapper with `Device`; `hidapi`, the cython one with `device`). The code handles both, CI and the binary use `hidapi`, the README says `pip install hid`. A machine with both installed could import the wrong one. | `connect()` branches on `hasattr(hid, "Device")`; `build-release.yml` installs `hidapi`; README | Not a failure today, a trap for source installs. | `pip list` on the laptop; `python -c "import hid; print(hid.__file__, hasattr(hid, 'Device'))"`. |
| W5 | Opening the device twice at once (the Linux `flock` is a no-op on Windows) probably gives each handle its own input queue, so a live-test run and a manual `info` would not corrupt each other but would both see the stream. | `test_device_live.py` lock | Probably harmless, but the lock gives no protection on Windows. | Open two `info` runs at the same time; both should finish. |

If you want any of W1 to W5 turned into a CI test or a probe script, say which; W1 is the only one
the mock can prove.
