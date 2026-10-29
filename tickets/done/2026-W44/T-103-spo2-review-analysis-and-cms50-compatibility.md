# T-103: Analyse SpO2 Review; download compatibility matrix for the CMS50 family

- **Status:** Done (SpO2 Review unavailable)
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](../../open/T-061-po250-po300-download-recordings.md)
- **Related:** [T-098](T-098-identify-po250-po300-oem-model-and-software.md),
  [T-100](T-100-map-spo2exe-device-table-and-transports.md),
  [T-101](T-101-download-recordings-from-other-models.md)
- **Scope & Relevant Files:**
  - `archive/` (the SpO2 Review installer/binary, once obtained; not in git)
  - `PROTOCOL.md` (new section), `README.md` (supported models)

---

## Description & Context

psytrap request (2026-10-29). Contec's PC software comes in two generations:
**SpO2 Assistant** (`SpO2.exe`, CMS50E/F/I and the PO-400, `.SpO2` files) and
the older **SpO2 Review** (CMS50D+ and similar, `.spoR`/`.spo` files). Only
`SpO2.exe` is in the repo; SpO2 Review has never been looked at.

Two parts:
1. **SpO2 Review:** get the installer (Contec/Pulox download pages, or a
   CMS50D+ CD image), store it under `archive/`, and analyse it statically like
   `SpO2.exe`: transport (USB-serial chip and IDs), commands and replies for
   listing and downloading stored recordings. Its file format is out of scope
   (psytrap, 2026-10-29: "download recording from device is the task").
   Compare with OSCAR's `cms50_loader.cpp`, which talks to the same devices.
2. **Compatibility matrix** for the CMS50 family (CMS50D+, CMS50E, CMS50F,
   CMS50I, others found on the way) and the Pulox rebadges (PO-200, PO-250,
   PO-300, PO-400): per model the USB interface (HID or USB-serial and IDs),
   the vendor software, the protocol (`SpO2.exe`'s, OSCAR's `cms50_loader`, or
   OSCAR's `cms50f37_loader` `7D 81` framing), whether OSCAR downloads it, and
   what `fiedle400` would need to download it (nothing / USB ID / transport /
   protocol). Each cell marked with its evidence (source code,
   static analysis, listing, forum report) or "unknown".

No device needed. No live/realtime mode (psytrap, 2026-10-29), only stored
recordings.

## Criteria

- [x] SpO2 Review obtained and stored under `archive/`, or recorded as unavailable
      (unavailable: the known download link is dead, psytrap 2026-10-29)
- [x] Its download protocol documented, compared with OSCAR's
      `cms50_loader.cpp` (OSCAR's side only, `PROTOCOL.md` §6.1 protocol A; SpO2 Review
      itself could not be analysed)
- [x] Compatibility matrix written (in `PROTOCOL.md` or its own doc), every cell
      with evidence or "unknown" (`PROTOCOL.md` §6)
- [x] T-061 and its subtickets updated with the result

## Execution Notes

2026-10-29 (cloud, desk research only):

- **Matrix:** `PROTOCOL.md` §6. Three protocols, not two: A = CMS50 legacy (OSCAR
  `cms50_loader`, 19200 8O1, device pushes one recording), B = CMS50F v3.7 (OSCAR
  `cms50f37_loader`, 115200 8N1, `A3`..`A6` listing/download, replies with bit 7 clear,
  no checksum), C = the PO-400's protocol (this repo).
- **B is not C** (corrects `PROTOCOL.md` §5 as written for T-101): a scan of every
  constant-opcode call to `SpO2.exe`'s send helper `0x4bc385` finds none of B's commands, and
  B's reply format is the opposite bit-7 convention to C's. SpO2 Assistant 3.1.0.4 therefore
  cannot download a protocol-B device. §3.12's `A5`/`A6` are B's commands.
- **Unknown, cheap to settle locally:** whether the PO-400 also answers B's read-only `7D 81 A8`
  (model) and `7D 81 A9` (vendor). Never send B's `AE` (erase) or `AA`.
- **SpO2 Review:** located (v1.2 `spo2setup_gen_1.2.zip` on rehmann.co via luke.lol; v1.0 on
  pulseoxstore.com) but the cloud's network policy blocks those hosts, and psytrap found the
  link dead (2026-10-29). Recorded as unavailable; protocol A is taken from OSCAR's
  `cms50_loader.cpp` alone. Ticket closed.
- **Follow-up candidates (not created):** protocol B support (CMS50F 3.7/CMS50I/CMS50H, reuses the
  serial backend, mock-testable from OSCAR's source); protocol A support (older models).
