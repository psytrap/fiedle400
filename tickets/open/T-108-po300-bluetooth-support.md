# T-108: PO-300 Bluetooth support

- **Priority:** Low
- **Owner:** Either
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-105](T-105-cms50f37-protocol-b-download.md) (protocol B engine, now being
  built for the PO-250), [T-102](T-102-po300-owner-test-run.md) (psytrap's own PO-300
  teardown), [docs/CMS50_COMPATIBILITY.md](../../docs/CMS50_COMPATIBILITY.md) findings 9-11
- **Scope & Relevant Files:**
  - `docs/CMS50_COMPATIBILITY.md` (finding 9: the vendor protocol doc)
  - Whatever Bluetooth/`rfcomm` discovery and pairing needs on Linux and Windows
  - `fiedle400/serial_port.py`, a protocol-B engine (shared ground with T-105)

---

## Description & Context

Some PO-300 units support Bluetooth -- the PO-300 manual's symbol legend has an entry
marked "only on devices with Bluetooth" (session note, 2026-11-04), and psytrap's own
unit was opened as part of [T-102](T-102-po300-owner-test-run.md)'s teardown.

**This is not a separate protocol from protocol B.** Contec's own vendor spec
("Communication Protocol of Pulse Oximeter V7.0", 2010-07-08, found in a
`Contec-CMS50EW` GitHub repo -- `docs/CMS50_COMPATIBILITY.md` finding 9) states
Bluetooth is presented to the host as a virtual COM port (SPP/`rfcomm`): same command
set as protocol B over USB-serial, different transport only.

**Status update (2026-11-04): the hold on protocol B is lifted, but only for the PO-250**
([T-105](T-105-cms50f37-protocol-b-download.md), now `Owner: Cloud`). The PO-300 is
explicitly *not* covered by that -- psytrap's "protocol B" read on the PO-300
(`docs/CMS50_COMPATIBILITY.md` finding 11) is their own working guess, stated as such
("I guess Protocol B"), not a device confirmation, and it still needs its own decision
before any PO-300-specific engine work starts. T-105's engine work is reusable ground
once it exists (there is only one protocol B), but this ticket should not assume
PO-300 support follows automatically just because T-105 is moving.

Bluetooth adds its own platform work on top of whatever protocol-B engine exists:
device discovery/pairing (differs by OS), `rfcomm` binding on Linux, the Windows
Bluetooth COM-port equivalent, and deciding whether `fiedle400` auto-discovers a
paired device or requires an explicit port like protocol C's serial fallback does
today.

## Criteria

- [ ] `fiedle400 info` run against psytrap's own PO-300 (T-102) to confirm serial vs HID
      and the actual model string -- the one thing that would turn finding 11's guess
      into a real confirmation, before any PO-300 engine work starts
- [ ] psytrap confirms PO-300 protocol-B/Bluetooth support as its own scope decision
      (not inherited from T-105's PO-250 scoping)
- [ ] If in scope: Bluetooth discovery/pairing approach decided for Linux and Windows
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
