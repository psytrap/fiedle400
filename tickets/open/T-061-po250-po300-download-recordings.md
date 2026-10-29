# T-061: PO-250 / PO-300 support: download stored recordings from the device

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/engine/`, `fiedle400/hid_driver.py` (transport), `fiedle400/cli.py`
  - `PROTOCOL.md` (§5 other devices), `README.md` (supported models)

---

## Description & Context

psytrap request: support the Pulox PO-250 and PO-300, other models of the same
Contec-derived family as the PO-400.

**Scope (psytrap, 2026-10-29):** "download recording from device is the task";
"no live recording", "Only download recordings". So: find the device, list its
stored recordings (`sessions`) and download them (`download`, the wizard). No
live/realtime streaming, no erase, and no reading of other software's files
(T-099 was dropped for that reason).

Nobody on the project owns either model ("We have none of these devices. Can we
do it just with OSCAR and reverse engineering SpO2 App?"), so the work is built
from `SpO2.exe` and the vendor documents, mock-tested, and confirmed by the first
owner who runs it.

---

## Criteria

- [ ] `fiedle400` finds a PO-250/PO-300 and says which model it is (T-104)
- [ ] `sessions` and `download` work for it, read-only (T-101)
- [ ] `README.md` lists the models as "untested on real hardware" until an owner
      confirms, then as supported (T-102)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Subtickets

| Ticket | What | Needs a device? | Status |
| :---: | :--- | :--- | :--- |
| [T-098](../done/2026-W44/T-098-identify-po250-po300-oem-model-and-software.md) | Which hardware and PC software each model is | No | Done |
| [T-100](../done/2026-W44/T-100-map-spo2exe-device-table-and-transports.md) | `SpO2.exe`'s device table and its serial path | No | Done |
| [T-104](T-104-detect-po250-po300-po400-for-wizard-and-info.md) | Detect PO-250/PO-300/PO-400 for the wizard and `info` | Mock tests; an owner confirms | Open |
| [T-101](T-101-download-recordings-from-other-models.md) | Download stored recordings | Mock tests; an owner confirms | Open |
| [T-102](T-102-sample-file-from-po250-po300-owner.md) | An owner runs it (and, ideally, a USB capture) | An owner, not psytrap | Open |
| [T-103](T-103-spo2-review-analysis-and-cms50-compatibility.md) | CMS50 family download compatibility matrix | No | Open |
| [T-099](../done/2026-W44/T-099-read-other-vendor-oximetry-files.md) | Read other vendors' files | -- | Won't Do |

Order: T-104, then T-101, then T-102 when an owner is found.

## Findings so far (T-098, T-100; 2026-10-29)

- **PO-250** ships with **SpO2 Assistant** (its manual says so); a forum owner saw SpO2
  Assistant recognize it. One recording of up to 24 h, 2 x AAA.
- **PO-300**: Auto mode (up to 99 recordings, 72 h) plus Manual mode (24 h), the PO-400's two
  storage modes, so most likely the PO-400's own firmware family. Rechargeable; the USB cable
  also charges it.
- **`SpO2.exe` sends the PO-400's command frames on every transport** (HID and USB-serial at
  115200 baud) and picks devices by USB ID only: HID `28E9:028A` (PO-400) and `0483:5751`;
  serial `10C4:EA60`, `1CBE:0002`, `0483:5740` and ports named `STM32`/`USB` (`PROTOCOL.md` §5).
  The model is read from the device (`0xF1` model string), not from the ID.
- So if a model is HID with one of those IDs, today's engine should nearly work; if it is
  USB-serial, it needs a serial transport under the same engine (T-101). Not yet known: each
  model's actual VID:PID and model string; T-104 makes `fiedle400` report them.

## Execution Notes

<!-- Filled in on completion -->
