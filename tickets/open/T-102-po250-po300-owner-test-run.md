# T-102: A PO-250/PO-300 owner runs fiedle400 on their device

- **Status:** Open (deferred)
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

<!-- Filled in on completion -->
