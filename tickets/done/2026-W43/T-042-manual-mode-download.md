# T-042: Download Manual-mode recordings

- **Status:** Done
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - new `fiedle400/protocol/manual.py` (commands, `0xD0` header, subframe decoder)
  - `fiedle400/engine/device.py` (`list_sessions`, `read_manual_header`, `download_manual`)
  - `fiedle400/protocol/models.py` (`SessionInfo.manual`), `fiedle400/cli.py` (listings)
  - `tests/test_manual_mode.py`, `tests/fixtures/manual-download.trace.json`, `tests/hwsim.py`
  - `PROTOCOL.md` §3.14, `DESIGN.md`

---

## Description & Context

psytrap (2026-10-21): "manual mode should be implemented". A PO-400 in Manual recording mode
keeps one recording that `0x9C`/`0x9D` cannot see; SpO2 Assistant reads it with `A0` (header),
`A3` (SpO2), `A2` (pulse) and `A7` (block ack). psytrap's capture
`archive/capture/bum400_20261015_194301.pcap` shows the whole exchange.

---

## Criteria

- [x] `fiedle400 sessions`, `download` and the wizard list and download the Manual-mode
      recording, marked "(Manual mode)".
- [x] The commands are byte for byte what SpO2 Assistant sends; nothing destructive is sent.
- [x] The decoder matches `SpO2.exe`'s and is tested against the capture.
- [x] A lost reply is asked for again from the missing subframe.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-21 (Claude, cloud, patch 0030). Not yet run on a real device: that check is in
`tickets/INDEX.md`, "Open questions".

**How it works.** `list_sessions` sends the `A0` header query only when the Auto list is empty
(a device in Manual mode has no `0xEC` entries; Auto-mode devices with recordings never see
`A0`). A recording found that way is session 1 with `SessionInfo.manual = True`, and
`download_session` passes it to `download_manual`: `80`, `A3 00`, `A7 01`, `A2 00`, `A7 00`,
`A3 7F`, `A2 7F`, as in the capture. Records have the usual shape, one per second from the
header's start time; seconds without a finger are empty with flag `probe-out`.

**What `SpO2.exe` showed** (static, `archive/bruteforce/SpO2.exe`):
- Header parser `0x4e92ac`: the sample count is `D0` bytes 10..12, 7-bit little-endian, not
  bytes 8..10 as PROTOCOL.md had it (both read 59 in the capture by chance). Byte 1 is a kind
  (0, 1 or 4).
- Download dialog `0x4b75c6` (`D3`): each subframe adds 27 samples, cut at the header's count.
  A subframe number other than the next expected one makes it send `A3 7F` and `A3 00` from
  the missing subframe.
- Decoders `0x4e9440` (SpO2) and `0x4e97ce` (pulse): nibble `0xF` is an invalid sample, not an
  end marker, and the values after it stay invalid. The pulse decoder accepts `0x7F` as a
  first value, so no-finger subframes decode to noise for pulse; `fiedle400` keeps a pulse only
  where SpO2 is valid.
- Send helper `0x4bc385` for `A2`/`A3`: byte 1 = mode, bytes 2..3 = start subframe in 7-bit
  halves.

The capture decodes to 59 seconds: 27 without a finger, 14 measured (SpO2 96-97, pulse 57-71),
18 without. The old "decoded reference capture" table in PROTOCOL.md is replaced.
