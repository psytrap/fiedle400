# PO-x00 serial emulator (Arduino Uno)

A stand-in for a USB-serial PO-250 / PO-300 (or a PO-400 over serial), to try fiedle400's
serial backend (T-101, T-104, T-105) on a real serial port. It answers the probe, `info`,
`sessions` and `download` with the same recorded replies the mock tests replay.

**The replies are recorded from other devices, not from a PO-250 or PO-300.** Nobody on the
project has captured either of those models (T-102). In protocol C (PO-300, PO-400) it answers
with the PO-400's replies (`tests/fixtures/cli-exchange.trace.json`,
`tests/fixtures/manual-download.trace.json`): SpO2 Assistant sends the PO-400's commands to every
model (PROTOCOL.md §5). In protocol B (PO-250, CMS50F; `docs/PROTOCOL_B.md`) it replays a real
CMS50F 3.7 download from 2014 (`tests/fixtures/cms50f37-download.trace.json`): the PO-250 speaks
that protocol (kaivol/pulox, T-105). Both are the best guess, not a proof that a real model works.

**Model selection is by sketch, not jumper** (psytrap, 2026-11-04: jumpers were error-prone to
keep straight across sessions). Flash the sketch matching the model you want:

| Sketch | Model | 0xF1 / A8 model string | Storage it answers for |
| :--- | :--- | :--- | :--- |
| `serial-emulator/` (the default) | PO-250, protocol B | `EMU-250` (placeholder; the real one is unknown) | One recording, 2014-08-03 03:18:48: `A4` announces 20,904 samples, `A6` sends the 8,202 the capture holds, then goes quiet (fiedle400 warns about the rest) |
| `serial-emulator-po300/` | PO-300 | `EMU-300` (placeholder; the real one is unknown) | Auto: one 214 s recording; Manual: one 59 s recording |
| `serial-emulator-po400/` | PO-400 (as captured, over serial) | `50F` | as the PO-300 |
| `serial-emulator-cms50f/` | CMS50F 3.7, protocol B | `CMS50F` | as the PO-250, but fiedle400 refuses it by its model string and never gets to `sessions`/`download` |

Each derivative sketch is a thin wrapper (`#define DEFAULT_MODEL ...` plus the same
fault-jumper/setup/loop code) over the shared `emulator.h` core, reached via a symlink in the
sketch's own folder (`emulator.h`, `trace_data.h` -- Arduino's build only looks inside the
sketch folder itself, not `../`, so a plain relative include doesn't work here). Since T-105 the
PO-250 speaks protocol B, not the PO-400's protocol C with a Manual-only list (the earlier
`EMU-250` mode); the PO-300 question (whether it is really protocol B too) is T-108, not yet
answered by this emulator either way.

In protocol B the emulator answers `A7`/`A2` (`0C 80`), `AD`, `A8`, `A3`, `A4`, `A5` and `A6`
for recording #1, every byte with bit 7 set and without padding, as the capture shows. The
samples are stored as runs of (SpO2, pulse, count) in `trace_data.h` (about 4 KB of flash).
`AE` (erase) and `AA` are never answered.

The real limits (PO-300: up to 99 Auto recordings; PO-250: several recordings) are not emulated: there is no captured data for them, and an Uno has 2 KB of RAM.
fiedle400 asks for the Manual header only when the Auto list is empty, so the PO-400 and
PO-300 settings show the Auto recording only.

Fault jumpers (to GND, read before every command, so they can be changed while it runs):

| Pin | Fault | What fiedle400 should do |
| :--- | :--- | :--- |
| D2 | silent: reads everything, answers nothing | probe fails ("did not answer like an oximeter") |
| D3 | bad checksum: last byte of every reply report off by one | probe fails; download drops frames and warns |
| D4 | split: 20 ms pause in the middle of every 64-byte report | still works (the reports are put back together) |
| D5 | unpadded: replies without their zero padding | Manual download works; Auto download loses records (see below) |

The LED (D13) toggles on every command and stays lit once a destructive command (erase)
arrived. The emulator never erases anything and never answers one; fiedle400 refuses `clear`
on serial ports anyway (T-104).

## Flash

Arduino IDE: open `serial-emulator/serial-emulator.ino` (or one of the model folders below),
board "Arduino Uno", Upload. Or with arduino-cli, naming the folder for the model you want
(default PO-250 shown; swap in `serial-emulator-po300`, `serial-emulator-po400` or
`serial-emulator-cms50f` for the others):

```
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno hardware/serial-emulator
arduino-cli upload  --fqbn arduino:avr:uno -p /dev/ttyACM0 hardware/serial-emulator
```

For a derivative, point at its own folder instead, e.g.
`hardware/serial-emulator/serial-emulator-po300`.

Before T-105 it used 5.8 KB of flash and 466 bytes of RAM (checked with avr-gcc 7.3 and the
Arduino AVR core 1.8.6, not with arduino-cli). The protocol-B data adds about 4.1 KB of flash and
no RAM beyond a few stack bytes; not rebuilt with avr-gcc since (the cloud has none), so check
the size line when you upload. 115200 baud is reliable on a genuine Uno: the ATmega328P and the
16U2 USB chip both run at 16 MHz and land on the same 117 647 baud. A CH340 clone runs at an
exact 115 200, 2.1 % off, which is within 8N1's tolerance.

## The auto-reset on open

Opening the port resets an Uno (DTR), and the bootloader then swallows the first bytes for
about a second. fiedle400 probes for 0.3 s right after opening, so the probe fails. Either:

- put a 10 µF capacitor between RESET and GND (take it out to upload again), or
- on Linux, once after plugging in: `stty -F /dev/ttyACM0 -hupcl`, then wait 2 s. DTR then
  stays up between runs, so later opens do not reset the board.

## Run fiedle400 against it

A Uno's USB ID (genuine `2341:0043`, CH340 clone `1A86:7523`) is not one SpO2 Assistant scans
for, so fiedle400 does not find it by itself. Name the port, **after** the command (a `-d`
before the command is ignored):

```
fiedle400 info     -d /dev/ttyACM0      # Linux, genuine Uno (clone: /dev/ttyUSB0)
fiedle400 sessions -d /dev/ttyACM0
fiedle400 download -d /dev/ttyACM0 -f csv -o emu.csv
fiedle400 info     -d COM5              # Windows (see Device Manager)
```

An Uno is already a USB-serial device (a genuine one is USB CDC ACM through its ATmega16U2, a
clone a CH340), so nothing has to be faked on the USB side. It keeps its stock USB ID, which
is why the port is named with `-d`.

On Linux the user needs the `dialout` group. Expected, with the default PO-250 sketch flashed:
`info` shows "Pulox PO-250 (protocol B, model string "EMU-250")" and an untested-model note,
`sessions` one recording of 5h 48m 24s from 2014-08-03 03:18:48, and `download` 8,202 records
with a warning that 12,702 are missing (the capture ends there; about 2 s on the line). Flash
`serial-emulator-po300` instead and `info` shows "Unknown PO-x00 family device" (`EMU-300`);
flash `serial-emulator-po400` and `info` shows model `50F`; either way `download` gets 214
records. Flash `serial-emulator-cms50f` and every command stops at the connect: "Found a CMS50F
device ... only for the PO-250". Verified against a real Arduino Uno R3 for all four sketches
(psytrap, 2026-11-04).

## Without a board

The core (`emulator.h`) also builds for a PC and serves a pseudo-terminal, which is how it is
tested here (`tests/test_serial_emulator.py`):

```
g++ -O2 -o /tmp/host_sim hardware/serial-emulator/host_sim.cpp
/tmp/host_sim /tmp/ttyACM-emu po250 &        # the default; or po300, po400; faults: e.g. "split"
fiedle400 download -d /tmp/ttyACM-emu -f csv -o po250.csv
/tmp/host_sim /tmp/ttyACM-emu cms50f &       # protocol B, named CMS50F: fiedle400 should refuse it
fiedle400 info -d /tmp/ttyACM-emu
```

## Changing the data

`trace_data.h` is generated from the fixtures: `python3 hardware/serial-emulator/make_trace.py`.
The test fails when it is stale. A different model string: `MODEL_STRING_OVERRIDE` in whichever
sketch you are flashing (each derivative has its own copy of that line).

## What it found (2026-10-29, on the PC build)

- With D5 (unpadded), the Auto download drops frames and returns 164 of 214 records: fiedle400's
  parsers assume each reply starts a 64-byte report. If a real serial model does not pad its
  replies, that has to be fixed (T-102).
- With D3, `info` still prints model `50F` after the probe rejected it, and `sessions` lists the
  recording: only the probe and the download check checksums.
- With D2 and `-d`, `sessions` says "No stored recording sessions found" instead of saying the
  device does not answer.

## What it found (2026-10-29, on a genuine Uno)

- Flashed and run against a real Arduino Uno R3 at `/dev/ttyACM1` (`stty -F ... -hupcl` to
  survive the DTR auto-reset between commands). `info`, `sessions` (214 records, 3m34s) and
  `download -f csv` (214/214 records, 428 packets, 0 sequence gaps) all correct with
  `DEFAULT_MODEL` set to `EMU_PO300` (no jumper).
- **Found a real bug this way, not visible on the PC build**: `info` showed the model as
  `"EMU-300 8"` -- `fiedle400/engine/device.py`'s `0x81`->`0xF1` handler read 9 bytes
  (`fw_report[1:10]`) instead of the 8 model bytes (`fw_report[1:9]`), leaking the checksum
  byte into the displayed model whenever that byte happens to be alphanumeric. Invisible with
  the real PO-400's `"50F"` (checksum `0x3C` / `'<'`, filtered out by the alnum/`-_ ` cleanup)
  but not with `"EMU-300"` (checksum `0x38` / `'8'`, alphanumeric). Fixed; regression test
  `tests/test_serial_port.py::TestModelStringChecksumByteIsNotPartOfTheModel`.
- `clear` correctly refused on the serial port ("download-only in fiedle400").

## What it found (2026-11-04, model jumpers replaced with derivative sketches)

- Split the old D6/D7/D8 model jumper into three sibling sketches
  (`serial-emulator-po300/`, `serial-emulator-po400/`, `serial-emulator-cms50f/`), each sharing
  `emulator.h`/`trace_data.h` with the default `serial-emulator/` (PO-250) sketch via a symlink
  in its own folder -- a plain `../emulator.h` include does not work because `arduino-cli`'s
  build only looks inside the sketch folder itself.
- All four compile clean on `arduino:avr:uno` (about 9.8 KB flash, 503 bytes RAM each) and were
  flashed and run against the real Arduino Uno R3 at `/dev/ttyACM1` in turn: PO-250 (`info`,
  `sessions` 1×20,904 samples announced/8,202 received, `download`, `clear` correctly refused),
  PO-300 (`EMU-300`, 214 records), PO-400 (`50F`, 214 records), CMS50F (correctly refused at
  connect). Matches the mock/PC-build behaviour exactly.
