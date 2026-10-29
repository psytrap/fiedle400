# T-105: Download from CMS50F v3.7 / CMS50I (protocol B)

- **Status:** Open (deferred, on hold)
- **Priority:** Low
- **Owner:** Either
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-103](../done/2026-W44/T-103-spo2-review-analysis-and-cms50-compatibility.md)
- **Scope & Relevant Files:**
  - `CMS50_COMPATIBILITY.md` (protocol B, §1 and §6)
  - `fiedle400/serial_port.py` (probe), a new protocol module and engine
  - `drafts/T-105-cms50f37-engine.diff`; the captures in `archive/capture/cms50f37-2014/` (not in git)

---

## Description & Context

The CMS50F with firmware 3.7, the CMS50I and the CMS50H speak protocol B (OSCAR's
`cms50f37_loader`), which is not the PO-400's protocol (`CMS50_COMPATIBILITY.md` §2). A 2014
serial capture of SpO2 Assistant 2.x downloading a CMS50F 3.7 confirms it byte for byte (§6).

**On hold (psytrap, 2026-10-29):** "Then lets put it on hold just document." and "We will only
support Po-250 and po-300". Do not start without psytrap asking.

A draft was written before the hold (2026-10-29, cloud):
`drafts/T-105-cms50f37-engine.diff`, against v0.5.5 (`git apply` it to try). It adds
`fiedle400/protocol/cms50f37.py` (9-byte requests, frame splitter, model/date/duration/sample
decoders), a read-only `fiedle400/engine/cms50f37.py` (`info`, `sessions`, `download`; erase,
clock and live mode refused, `AE` never sent), a protocol-B fallback in the serial probe after
the PO-x00 probe (`80`×7, then `A7` `A2` `A8`), `serial_engine.make_engine()` to pick the engine,
and the capture as `tests/fixtures/cms50f37-download.trace.json`. Its replay tests were not
written yet, and the existing suite was not re-run after the probe change.

## Criteria

- [ ] psytrap lifts the hold
- [ ] Engine replays the 2014 capture: 1 recording, 2014-08-03 03:18:48, 20,904 samples
      announced, 8,202 received, warning for the missing rest
- [ ] Probe order keeps PO-x00 devices on their own protocol (no B command reaches them unless the
      PO-x00 probe failed)
- [ ] Erase is never sent to a protocol-B device
- [ ] An owner of a CMS50F 3.7 or CMS50I confirms a download

## Execution Notes

<!-- Filled in on completion -->
