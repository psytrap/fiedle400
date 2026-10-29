# T-103: Analyse SpO2 Review; download compatibility matrix for the CMS50 family

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-098](../done/2026-W44/T-098-identify-po250-po300-oem-model-and-software.md),
  [T-100](../done/2026-W44/T-100-map-spo2exe-device-table-and-transports.md),
  [T-101](../done/2026-W44/T-101-download-recordings-from-other-models.md)
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

- [ ] SpO2 Review obtained and stored under `archive/`, or recorded as unavailable
- [ ] Its download protocol documented, compared with OSCAR's
      `cms50_loader.cpp`
- [ ] Compatibility matrix written (in `PROTOCOL.md` or its own doc), every cell
      with evidence or "unknown"
- [ ] T-061 and its subtickets updated with the result

## Execution Notes

<!-- Filled in on completion -->
