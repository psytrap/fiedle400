# T-104: Detect PO-250 / PO-300 / PO-400 for the wizard and `info`

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-101](T-101-download-recordings-from-other-models.md) (uses the result),
  [T-102](T-102-po250-po300-owner-test-run.md) (an owner runs it)
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

- [ ] Device search accepts the HID IDs above; serial candidates listed with "not supported yet"
- [ ] Model taken from the `0xF1` model string; PO-400 still shown as PO-400
- [ ] `info` and the wizard show model, VID:PID, transport and raw model string
- [ ] Unsupported model: clear message plus a pointer to send the `info` output, no traceback
- [ ] Mock tests for each ID and for an unknown model string; tests pass

## Execution Notes

<!-- Filled in on completion -->
