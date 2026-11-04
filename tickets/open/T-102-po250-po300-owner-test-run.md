# T-102: A PO-250/PO-300 owner runs fiedle400 on their device

- **Priority:** Normal
- **Owner:** Local
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-095](T-095-beta-rollout-advertise-and-find-users.md) (finding
  users), [T-059](T-059-funding-license-for-additional-devices.md) (funding devices)

---

## Description & Context

T-104 and T-101 are built from `SpO2.exe` and the manuals, and only mock-tested.
Only a real device proves them. Ask in the beta rollout (T-095) for owners of a
PO-250 or PO-300 to:
1. run `fiedle400 info` and send its output (USB VID:PID, model string; T-104);
2. once T-101 is built, run `sessions` and `download` on a short test
   recording, and send the vendor software's CSV of the same recording as the
   answer key;
3. ideally, capture the vendor software downloading it (Wireshark/USBPcap on
   Windows), like the PO-400 captures in `archive/capture/`.

Privacy: recordings are health data; ask for a short test recording, store it
under `archive/` (not in git) unless the owner agrees to publish it.

## Criteria

- [ ] Request text added to the T-095 outreach
- [ ] `info` output received per model, or recorded as unavailable
- [ ] T-101's download tried by the owner; values equal the vendor's CSV

## Execution Notes

**2026-11-04 (local): psytrap owns a PO-300 and opened it.** Board marked
Rev E. Main-package top marking read by eye (no photo yet): line 1
`?32ARNY??` (both ends unclear), line 2 `430F247` (clear). This is
**TI MSP430F247** -- a real part (64-pin LQFP, 32KB flash, 4KB RAM,
12-bit ADC, comparator, I2C/SPI/UART), and the clear line matches it
exactly with no worn/missing digits needed, unlike the earlier F2417
guess. Not yet cross-checked against TI's own package marking diagram
for this exact part. Line 1 is presumed a lot/date code, not decoded.

Note: F247 is a general-purpose low-power MSP430, not one of TI's parts
with an integrated photoplethysmography front end (e.g. FG437/FG461x) --
if this ID is right, SpO2 signal conditioning lives in separate board
components, not on-chip.

**Second chip found next to it:** marked `M430F2132`, both chips clocked
at 8MHz. **TI MSP430F2132** -- also a real part, smaller than the F247
(28-TSSOP, 8KB flash, 512B RAM, 10-bit ADC, 24 I/O, one USCI). So the
board carries two MSP430s. Unconfirmed hypothesis: the F247 runs the
application layer (display, buttons, USB/UART) while the F2132 is a
dedicated front-end controller for the SpO2 sensor (LED drive timing,
photodiode ADC sampling) -- plausible given the role split, but could
equally be an unrelated second-source/revision choice.

**PCB silkscreen label:** reads approximately `CMS7..820.026.01/1.4`
(gaps between `CMS7` and `820` unclear); the `CMS7` prefix itself is
clear, not a misread of `CMS5`. No external match found for `820.026`
against any Contec model or board number.

This sits oddly next to every other piece of evidence so far (OSCAR's
own description, the PO-250 cpaptalk report, the two-MCU pulse-ox
design), all of which point to the Pulox line being Contec CMS50-family
rebadges -- and Contec's own CMS70A is a different, bench-top product
(separate probe, not a finger-clip), so it's not a product-line match
on its face. Most likely explanation: `CMS7` is Contec's internal PCB
design-lineage prefix, not the finished product's own model family --
manufacturers commonly reuse a board-family code across unrelated
products as their design evolves, separate from the marketing model
name. Not confirmed; the full label (especially what sits between
`CMS7` and `820`) would help.

**Second board label:** `BMKT-758`. No external match found; likely an
internal PCB assembly/batch code, not a part with public documentation.

Further fragment-by-fragment reads of small labels are hitting
diminishing returns -- a full photo of the board would let a next pass
read everything at once instead of one unclear string at a time.

**No reset hole, inside the clip mechanism or out** -- psytrap's PO-400
has one; the PO-300 manual (`pulox.de/downloads/PO-300_Bedienungsanleitung.pdf`,
§6.1.6) describes squeezing the clip open and pressing a reset button
inside a `RESET` opening, with a figure (Fig.12) showing exactly that;
this unit has neither the opening nor the button, checked by opening
the clip itself, not just looking at the closed case.

This lines up with a second finding from the manuals (session note,
2026-11-04): the PO-300 manual's own symbol legend has a Bluetooth
entry marked "only on devices with Bluetooth" -- wording that only
makes sense if Pulox ships more than one PO-300 hardware revision
under one model name and one manual. The missing reset hole is a
second, independent sign of the same thing: this specific unit is a
hardware revision that the manual's own reset section does not
actually describe. Not confirmed which revision(s) map to which
protocol -- but it narrows "which PO-300 did the two contradicting
forum owners have" (`docs/CMS50_COMPATIBILITY.md` finding 6) from one
unexplained contradiction to a documented pattern of hardware variance
under the same model name.

This doesn't resolve this ticket's own criteria yet (no `fiedle400 info`
output gathered, no `sessions`/`download` run) -- it's a hardware-teardown
side finding from the same device, kept here since T-102 is the owner
most likely to also run the software-side checks.
