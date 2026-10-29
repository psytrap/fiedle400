# T-098: Identify the PO-250 / PO-300 hardware and their PC software

- **Status:** Done
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Scope & Relevant Files:**
  - `tickets/open/T-061-po250-po300-download-recordings.md` (result goes there)
  - `README.md` (supported-models line, once known)

---

## Description & Context

Desk research, no device needed. Pulox does not name the Contec model behind
the PO-250 or PO-300 in its shop listings. OSCAR only says Pulox "rebadge Contec
CMS50's ... such as the Pulox PO-200, PO-300, PO-400" (`oximeterimport.cpp`).
What is known from the listings (medpex, testberichte.de, Galaxus, 2026-10-29):
- PO-250: finger clip, 2 x AAA, OLED, internal memory with a record function,
  USB data cable, Windows software (download).
- PO-300: finger clip, rechargeable (about 21 h), colour display, one recording
  of up to about 24 h at a time that must be transferred before the next, a USB
  data cable that reviewers call non-standard, Windows software (download).

Forum report (cpaptalk.com t177946): a PO-250 owner found OSCAR does not
download from it (OSCAR lists only the CMS50D+, CMS50E, CMS50F and CMS50I), but
**SpO2 Assistant recognized the PO-250** -- so it likely speaks `SpO2.exe`'s
protocol like the PO-400. OSCAR's "Pulox PO-200, PO-300, PO-400 ... should also
work" is a hope, not a tested list.

For the PO-300, the single 24 h recording and the special cable match the CMS50D+ that OSCAR's
`cms50_loader.cpp` handles, but that is a guess.

Which protocol family a model uses decides everything else in T-061:
1. HID like the PO-400 (`SpO2.exe`'s HID list: `28E9:028A`, `0483:5751`);
2. USB-serial (`SpO2.exe`'s COM list: CP210x `10C4:EA60`, `0483:5740`,
   `1CBE:0002`, `0451:16AA`) -- OSCAR's CMS50 families;
3. the older "SpO2 Review" software (`.spoR` files) of the CMS50D+.

## Criteria

- [x] The PO-250's and PO-300's manuals (Pulox download page) read: Contec model
      or CE/registration number, the PC software's name and version, cable type
      (see Execution Notes: no Contec model and no notified-body number in either)
- [ ] If the vendor installer is downloadable: its driver files say which
      USB IDs it expects (CP210x driver = serial, none = HID) -- not found; the
      Pulox download page gave no installer link we could reach, so this moves to T-104
- [x] Result per model: protocol family 1, 2 or 3 above, with the evidence
- [x] T-061 updated

## Execution Notes

Done 2026-10-29 (cloud, desk research; no device).

Sources read: the PO-250 manual (`pulox.de/downloads/PO-250_Bedienungsanleitung.pdf`) and the
medpex leaflets `10121549` (PO-250) and `10121489` (PO-300). Both name only the distributor,
Novidion GmbH, Cologne, and the CE mark under 93/42/EEC, with no notified-body number and no
Contec model. Neither gives a software version or driver step.

| | PO-250 | PO-300 |
| :--- | :--- | :--- |
| PC software | **SpO2 Assistant** (named in the manual) | "PC-Software (Download)", Windows 2000 to 10; name not given |
| Cable | USB data cable | USB data and charging cable |
| Power | 2 x AAA | rechargeable |
| Storage | one recording, up to 24 h; starting a new one deletes the old; "Memory is full" then switches off | **Auto mode** up to 99 recordings, 72 h in total; **Manual mode** up to 24 h |
| Install note | "install the software first, then connect"; no driver | none |

**Result:**
- **PO-250: family 1 or 2 (SpO2 Assistant's protocol).** The manual ships it with SpO2
  Assistant, and the cpaptalk t177946 owner saw SpO2 Assistant recognize it while OSCAR did not.
  Whether it is HID or USB-serial is open; T-100 shows it does not matter for the commands, only
  for the transport.
- **PO-300: most likely family 1, the PO-400's own.** Its Auto mode (many recordings) plus
  Manual mode (one long recording) is exactly the PO-400's two storage modes (`0xEC` Auto
  sessions, §3.14 Manual), which no CMS50D+ has. That is an inference from the feature list,
  not a confirmed model string.
- **Family 3 (SpO2 Review, `.spoR`) is not indicated for either.** The earlier guess that the
  PO-300 is a CMS50D+ (single 24 h recording) is wrong: that describes the PO-250.

What is still unknown: each model's USB VID:PID and its `0xF1` model string. Both come from
the device itself; T-104 makes `info` and the wizard report them, so the first owner who runs
it answers this.
