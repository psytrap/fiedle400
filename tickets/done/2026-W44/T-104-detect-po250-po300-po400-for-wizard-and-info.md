# T-104: Detect PO-250 / PO-300 / PO-400 for the wizard and `info`

- **Status:** Done
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Related:** [T-101](T-101-download-recordings-from-other-models.md) (uses the result),
  [T-102](../../open/T-102-po250-po300-owner-test-run.md) (an owner runs it)
- **Scope & Relevant Files:**
  - `fiedle400/hid_driver.py` (device search), `fiedle400/protocol/hardware.py` (`KNOWN_DEVICES`)
  - `fiedle400/cli.py` (`command_info`, `run_interactive_wizard`)
  - `PROTOCOL.md` §5, `README.md`

---

## Description & Context

psytrap request (2026-10-29): "add ticket for po-250/po-300/po-400 discovery for
wizzard and info requests".

Today the device search only accepts `28E9:028A`, `info` prints "PULSOX PO-400"
whatever is attached, and the wizard says "no device" for anything else. With a
PO-250 or PO-300 plugged in, the user should instead learn what was found.

Discovery, read-only, no download:
1. **Find candidates** by the IDs SpO2 Assistant itself scans (`PROTOCOL.md` §5):
   HID `28E9:028A`, `0483:5751`; USB-serial `10C4:EA60`, `1CBE:0002`,
   `0483:5740`. Serial ports are only listed, not opened, until T-101 adds a
   serial transport.
2. **Identify the model** from the device, not the USB ID (SpO2 Assistant attaches
   no model to an ID): for a HID device, send `81 01` and read the `0xF1` model
   string (`"50F"` on the PO-400). Map known strings to PO-250/PO-300/PO-400;
   show an unknown string as it is.
3. **Report it:** `info` prints the detected model, VID:PID, transport and model
   string instead of a fixed "PO-400" heading. The wizard names the device it
   found; for a model `download` does not support yet, it says so and asks the
   user to send the `info` output (T-102), instead of failing or saying "no device".

`KNOWN_DEVICES` in `hardware.py` already labels `10C4:EA60` "CMS-50D+" and cites
installer INF files that are not in the repo; check those labels against
`PROTOCOL.md` §5 and mark anything unproven as such.

Never show a model the device did not report (project rule): an ID match alone
says "PO-x00 family device (model unknown)".

## Criteria

- [x] Device search accepts the HID IDs above; serial candidates are found too (and, with
      T-101 done in the same patch, used rather than listed as "not supported yet")
- [x] Model taken from the `0xF1` model string; PO-400 still shown as PO-400
- [x] `info` and the wizard show model, VID:PID, transport and raw model string
- [x] Unsupported model: clear message plus a pointer to send the `info` output, no traceback
- [x] Mock tests for each ID and for an unknown model string; tests pass

## Execution Notes

Done 2026-10-29 (cloud, with T-101; patch 0036). Mock tests only.

- `protocol.hardware`: `HID_USB_IDS`, `SERIAL_USB_IDS`, `MODEL_STRINGS` (only `"50F"` ->
  "Pulox PO-400", the one string seen on a real device), `describe_model()`, `is_known_model()`.
  An unknown string is shown as `Unknown PO-x00 family device (model string "…")`, a missing one
  as "model not reported"; nothing is guessed. `KNOWN_DEVICES` now lists the five SpO2.exe IDs
  with sources that are in the repo (`PROTOCOL.md` §5, OSCAR); the INF-file citations, which
  were not in the repo, are gone.
- `info`: heading "PULOX OXIMETER DEVICE & HARDWARE INFORMATION", a "Detected Model" line
  (model, USB HID/USB serial, VID:PID) and "Active Backend" (now also "USB serial"). For an
  untested model it ends with a request to send the `info` output to the project's issues.
- Wizard: "[✓] Detected Model" line plus the same request; erase is refused with a message for
  anything but the PO-400's USB ID (T-101).
- Not done: the `0xF1` strings of the PO-250/PO-300 are still unknown (T-102); `selftest` still
  checks HID only.
