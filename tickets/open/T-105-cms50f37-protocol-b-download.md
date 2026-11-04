# T-105: PO-250 download (protocol B)

- **Priority:** Normal
- **Owner:** Cloud
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-103](../done/2026-W44/T-103-spo2-review-analysis-and-cms50-compatibility.md),
  [T-102](T-102-po250-po300-owner-test-run.md), [T-108](T-108-po300-bluetooth-support.md)
- **Scope & Relevant Files:**
  - `docs/CMS50_COMPATIBILITY.md` (findings 9, 10, 11), `docs/PROTOCOL_B.md` (the wire spec)
  - `fiedle400/serial_port.py` (probe), `fiedle400/protocol/cms50f37.py`, a new read-only engine
  - `drafts/T-105-cms50f37-engine.diff`; the captures in `archive/capture/cms50f37-2014/` (not in git)
  - `hardware/serial-emulator/` (Arduino emulator: default model, PO-250 protocol-B download
    emulation, not just probe-and-refuse)

---

## Description & Context

The CMS50F with firmware 3.7, the CMS50I and the CMS50H speak protocol B (OSCAR's
`cms50f37_loader`), which is not the PO-400's protocol (`CMS50_COMPATIBILITY.md` §2,
`PROTOCOL_B.md`). A 2014 serial capture of SpO2 Assistant 2.x downloading a CMS50F 3.7
confirms it byte for byte (`CMS50_COMPATIBILITY.md` §6).

**Hold lifted (psytrap, 2026-11-04), scoped to the PO-250 specifically.** The original hold
(2026-10-29: *"Then lets put it on hold just document."* and *"We will only support Po-250 and
po-300"*) was about uncertainty, not a refusal to ever build this -- that uncertainty is now
much lower for the PO-250, from three independent sources
(`CMS50_COMPATIBILITY.md` finding 11 records the reasoning in full):

1. **Contec's own protocol spec** ("Communication Protocol of Pulse Oximeter V7.0", 2010-07-08)
   -- `CMS50_COMPATIBILITY.md` finding 9. Matches this project's protocol-B documentation
   byte-for-byte, and adds a full reason-code table, exact real-time bit layout, and
   device-notice/time-sync semantics this project didn't have before.
2. **A real, working open-source implementation** (`kaivol/pulox`, a Rust CLI, MIT licensed,
   archived) built and exercised by its own author against a **named PULOX PO-250** over serial
   -- `CMS50_COMPATIBILITY.md` finding 10. Its command set matches the vendor spec and this
   project's `PROTOCOL_B.md` exactly.
3. **The existing 2014 `.spm` wire capture and its originating forum report** (SleepyHead bug
   #207) -- already in this project's evidence (`CMS50_COMPATIBILITY.md` §6, `PROTOCOL_B.md` §5.1).

**This ticket is scoped to the PO-250, not general CMS50F/CMS50I/CMS50H support.** The underlying
protocol-B engine is the same code either way (there is only one protocol B), but `fiedle400`'s
model detection should gate actual support on the PO-250's own model string, the same way T-104
gates PO-250/PO-300/PO-400 detection today -- a generic CMS50-branded device should still be
refused, per psytrap's original scope decision. The PO-300 is a separate question
([T-108](T-108-po300-bluetooth-support.md)): finding 11's "protocol B" read on it is psytrap's
own working guess, not yet device-confirmed, and it may also need Bluetooth transport work this
ticket doesn't cover.

A draft was written before the hold (2026-10-29, cloud):
`drafts/T-105-cms50f37-engine.diff`, against v0.5.5 (`git apply` it to try). It adds
`fiedle400/protocol/cms50f37.py` (9-byte requests, frame splitter, model/date/duration/sample
decoders), a read-only `fiedle400/engine/cms50f37.py` (`info`, `sessions`, `download`; erase,
clock and live mode refused, `AE` never sent), a protocol-B fallback in the serial probe after
the PO-x00 probe (`80`×7, then `A7` `A2` `A8`), `serial_engine.make_engine()` to pick the engine,
and the capture as `tests/fixtures/cms50f37-download.trace.json`. Its replay tests were not
written yet, and the existing suite was not re-run after the probe change. **As written it
refuses every protocol-B device uniformly** (`PROTOCOL_B.md` §7); this ticket needs it changed to
support, not refuse, a device whose model string identifies it as a PO-250, while continuing to
refuse everything else that speaks protocol B.

**Emulator currently only probes and refuses protocol B -- not enough to test this ticket.**
`hardware/serial-emulator/README.md`'s D6+D8 jumper mode answers just the hello (`A7`/`A2`) and
model query (`A8`) so `fiedle400`'s probe can correctly identify and refuse it; there is no
protocol-B *download* emulation at all, and the current default model (no jumper) is PO-300, not
PO-250. With nobody on the project owning a real PO-250 (same gap T-102 is filling for the
PO-300), the emulator is the only way to mock-test this engine against believable protocol-B
traffic before an outside owner confirms it on real hardware -- the same mock-then-confirm
pattern T-101/T-104 already used for detection and download.

## Criteria

- [x] psytrap lifts the hold (scoped to PO-250; see above)
- [ ] Engine replays the 2014 capture: 1 recording, 2014-08-03 03:18:48, 20,904 samples
      announced, 8,202 received, warning for the missing rest
- [ ] Probe order keeps PO-x00 devices on their own protocol (no B command reaches them unless the
      PO-x00 probe failed)
- [ ] Model-string gate: a protocol-B device identifying itself as a PO-250 gets real support
      (`info`/`sessions`/`download`); any other protocol-B device (CMS50F/I/H, anything else)
      is still refused, same as today
- [ ] Erase is never sent to a protocol-B device
- [ ] Serial emulator defaults to PO-250 (no jumper needed); PO-300 moves to a jumper instead,
      matching this ticket's PO-250-first priority (update `hardware/serial-emulator/README.md`'s
      table and pin assignments accordingly)
- [ ] Serial emulator actually emulates protocol-B download for its PO-250 mode (real-time hello,
      model query, session list/length/start-time, and `A6` sample data replayed from the 2014
      capture or an equivalent fixture) -- not just probe-and-refuse like the current D6+D8 mode
- [ ] `fiedle400 download` against the updated emulator (PC build and, if practical, a genuine
      Uno) produces the same result as the capture replay test above
- [ ] `README.md` lists the PO-250 as supported for download, same convention as T-061's PO-300
      entry ("untested on real hardware" until an owner confirms)
- [ ] An owner of a real PO-250 confirms a download (psytrap does not own one; this needs an
      outside owner, same as T-102's role for the PO-300 -- cross-check against `kaivol/pulox`'s
      documented behavior in the meantime, as a secondary, non-device validation)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

<!-- Filled in on completion -->
