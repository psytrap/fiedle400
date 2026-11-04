# T-109: An owner of a real PO-250 confirms a download

- **Priority:** Normal
- **Owner:** Local
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Related:** [T-105](../done/2026-W45/T-105-cms50f37-protocol-b-download.md) (the engine this
  confirms), [T-102](T-102-po300-owner-test-run.md) (the equivalent ticket for the PO-300)

---

## Description & Context

[T-105](../done/2026-W45/T-105-cms50f37-protocol-b-download.md) built PO-250 download support
(protocol B) entirely without a real PO-250: Contec's own protocol spec, a third-party
open-source tool (`kaivol/pulox`) confirmed by its author against a real PO-250, and a 2014
capture of a different device in the same protocol family (a CMS50F, not a PO-250). No PO-250
reply has ever been seen by `fiedle400` itself.

**Split off from T-105 (psytrap, 2026-11-04) rather than blocking its close.** T-105 is now done
-- the engine, tests, docs and emulator are all built and verified (including against real
Arduino hardware emulating the protocol). PO-250 support ships marked **experimental** in
`README.md` precisely because this confirmation is still outstanding, matching how T-061 already
marks the PO-300 as "untested on real hardware" until T-102 closes.

## Criteria

- [ ] `fiedle400 info` output from a real PO-250 received and matches the engine's expectations
      (serial transport, protocol-B hello, a model string the gate accepts)
- [ ] `fiedle400 sessions` and `download` tried against it; downloaded values checked against the
      vendor software's own output for the same recording
- [ ] `README.md`'s "experimental" marker for PO-250 removed once confirmed, or kept with
      specifics recorded if something didn't match

## Execution Notes

<!-- Filled in on completion -->
