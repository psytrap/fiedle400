# T-061: PO-250 / PO-300 support via `.spo2` analysis

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/recording.py` (`read_spo2_file` and friends)
  - `SPO2_FORMAT.md`, `PROTOCOL.md`
  - `fiedle400/spo2_viewer.py`, `fiedle400/desat.py`

---

## Description & Context

psytrap request: support the Pulsox PO-250 and PO-300 (other models in the
same Contec-derived oximeter family) via `.spo2` *analysis*, not
necessarily live device download -- i.e. let `fiedle400 view`/the HTML
viewer open and analyze a `.spo2`/`.SpO2` file produced by one of these
other models, even without adding USB/HID protocol support for them.

This is a narrower, likely much cheaper ask than full device support: the
`.SpO2` binary file format is the vendor's shared **SpO2 Assistant** export
format across its device family (`SPO2_FORMAT.md`'s intro already says
so -- "CMS-50 series, CMS-60D, and Pulsox PO-400"), so a PO-250/PO-300
export may already decode correctly with the existing `read_spo2_file`/
`export.py` code, or need only minor field differences handled.

**Not yet known (this ticket needs to establish, not assume):**
- Whether a real PO-250 or PO-300 `.spo2`/`.SpO2` export is available to
  test against at all -- this is the actual blocker. Ties into
  [T-059](T-059-funding-license-for-additional-devices.md)'s funding ask
  for additional hardware, and possibly just needs a sample file from a
  PO-250/PO-300 owner rather than owning the device.
  Checking the model family's `.spo2` doesn't need the author to own one.
  `fiedle400` only needs one.
- Whether the record layout, sample rate, or any header fields differ
  from the PO-400's (`SPO2_FORMAT.md` §2) in a way that breaks decoding,
  or whether it's identical since SpO2 Assistant writes one shared format.
- Whether the desaturation-event detector's defaults (tuned/decoded
  against SpO2 Assistant, `SPO2_FORMAT.md` §7) still apply unchanged, or
  whether these simpler/older models use different default parameters in
  the vendor software.

---

## Criteria

- [ ] A real or vendor-documented PO-250/PO-300 `.spo2` sample obtained
      (or explicitly recorded as unavailable, blocking this ticket)
- [ ] Confirmed whether it decodes as-is with `read_spo2_file`, or what
      needs to change
- [ ] `SPO2_FORMAT.md`/`README.md` updated to state which models are
      supported via file analysis (distinct from live USB/HID device
      support, which stays PO-400-only unless a separate ticket adds it)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
