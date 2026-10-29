# PO-x00 serial emulator (Arduino Uno)

A stand-in for a USB-serial PO-250 / PO-300 (or a PO-400 over serial), to try fiedle400's
serial backend (T-101, T-104) on a real serial port. It answers the probe, `info`, `sessions`
and `download` with the same recorded replies the mock tests replay
(`tests/fixtures/cli-exchange.trace.json`, `tests/fixtures/manual-download.trace.json`).

**The replies are the PO-400's, not the PO-250's or PO-300's.** Nobody on the project has
captured either of those models (T-102). SpO2 Assistant sends the PO-400's commands to every
model (PROTOCOL.md §5), so this is the best guess, not a proof that a real PO-250/PO-300 works.

| Model (jumper) | 0xF1 model string | Storage it answers for |
| :--- | :--- | :--- |
| PO-400 (none) | `50F` (real) | Auto: one 214 s recording; Manual: one 59 s recording |
| PO-300 (D6 to GND) | `EMU-300` (placeholder; the real one is unknown) | as PO-400 |
| PO-250 (D7 to GND) | `EMU-250` (placeholder; the real one is unknown) | Manual only: one 59 s recording; the Auto list (`9C`) gets no answer |

The real limits (PO-300: up to 99 Auto recordings; PO-250: one Manual recording of up to
24 h) are not emulated: there is no captured data for them, and an Uno has 2 KB of RAM.
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

Arduino IDE: open `serial-emulator/serial-emulator.ino`, board "Arduino Uno", Upload.
Or with arduino-cli:

```
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno hardware/serial-emulator
arduino-cli upload  --fqbn arduino:avr:uno -p /dev/ttyACM0 hardware/serial-emulator
```

It uses 5.8 KB of flash and 466 bytes of RAM (checked with avr-gcc 7.3 and the Arduino AVR core
1.8.6, not with arduino-cli). 115200 baud is reliable on a genuine Uno: the ATmega328P and the
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

On Linux the user needs the `dialout` group. Expected: `info` shows model `50F` (or
"Unknown PO-x00 family device" with `EMU-300`/`EMU-250` and an untested-model note);
`download` gets 214 records (PO-400, PO-300) or 59 Manual records, 14 with a finger
(PO-250).

## Without a board

The core (`emulator.h`) also builds for a PC and serves a pseudo-terminal, which is how it is
tested here (`tests/test_serial_emulator.py`):

```
g++ -O2 -o /tmp/host_sim hardware/serial-emulator/host_sim.cpp
/tmp/host_sim /tmp/ttyACM-emu po250 &        # faults: add e.g. "split,badsum"
fiedle400 sessions -d /tmp/ttyACM-emu
```

## Changing the data

`trace_data.h` is generated from the fixtures: `python3 hardware/serial-emulator/make_trace.py`.
The test fails when it is stale. A different model string: `MODEL_STRING_OVERRIDE` in the sketch.

## What it found (2026-10-29, on the PC build)

- With D5 (unpadded), the Auto download drops frames and returns 164 of 214 records: fiedle400's
  parsers assume each reply starts a 64-byte report. If a real serial model does not pad its
  replies, that has to be fixed (T-102).
- With D3, `info` still prints model `50F` after the probe rejected it, and `sessions` lists the
  recording: only the probe and the download check checksums.
- With D2 and `-d`, `sessions` says "No stored recording sessions found" instead of saying the
  device does not answer.
