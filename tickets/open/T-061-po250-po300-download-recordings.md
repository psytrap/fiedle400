# T-061: PO-250 / PO-300 support: download stored recordings from the device

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

- [x] `fiedle400` finds a PO-250/PO-300 and says which model it is (T-104; mock-tested)
- [x] `sessions` and `download` work for it, read-only (T-101; mock-tested)
- [x] `README.md` lists the models as untested/experimental until an owner confirms (PO-250:
      experimental, T-105/T-109; PO-300: untested, T-102) -- still open: flipping either to
      plainly supported once confirmed
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Subtickets

| Ticket | What | Needs a device? | Status |
| :---: | :--- | :--- | :--- |
| [T-098](../done/2026-W44/T-098-identify-po250-po300-oem-model-and-software.md) | Which hardware and PC software each model is | No | Done |
| [T-100](../done/2026-W44/T-100-map-spo2exe-device-table-and-transports.md) | `SpO2.exe`'s device table and its serial path | No | Done |
| [T-104](../done/2026-W44/T-104-detect-po250-po300-po400-for-wizard-and-info.md) | Detect PO-250/PO-300/PO-400 for the wizard and `info` | Mock tests; an owner confirms | Done |
| [T-101](../done/2026-W44/T-101-download-recordings-from-other-models.md) | Download stored recordings | Mock tests; an owner confirms | Done |
| [T-102](T-102-po300-owner-test-run.md) | PO-300 owner runs it (psytrap's own unit; protocol/model still unconfirmed) | psytrap owns one | Open |
| [T-103](../done/2026-W44/T-103-spo2-review-analysis-and-cms50-compatibility.md) | CMS50 family download compatibility matrix | No | Done |
| [T-099](../done/2026-W44/T-099-read-other-vendor-oximetry-files.md) | Read other vendors' files | -- | Won't Do |
| [T-105](../done/2026-W45/T-105-cms50f37-protocol-b-download.md) | PO-250 download (protocol B) | Mock tests and the emulator | Done (v0.5.9); ships marked experimental |
| [T-109](T-109-po250-owner-confirmation.md) | PO-250 owner confirms a download (split from T-105's close) | An owner, nobody on the project owns one | Open |
| [T-108](T-108-po300-bluetooth-support.md) | PO-300 Bluetooth support -- separate from T-105's protocol-B engine | psytrap's own unit, once its protocol is confirmed | Open |

T-104, T-101 and T-105 are done. What's left is really just the **PO-300**: T-102 (psytrap's own
teardown and software-side checks, still missing `fiedle400 info`/`sessions`/`download` against
it), and T-108 (Bluetooth, blocked on T-102 confirming the protocol first). T-109 (an outside
PO-250 owner) is open too, but PO-250 already ships -- marked experimental -- so it isn't
blocking anything the way the PO-300 questions are.

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
  USB-serial, it needs a serial transport under the same engine (T-101, now built). Not yet
  known: each model's actual VID:PID and model string; `fiedle400 info` now reports them (T-104).

## CMS50 family (T-103, 2026-10-29)

- `CMS50_COMPATIBILITY.md`: the CMS50D+/E/older F (protocol A) and CMS50F v3.7/CMS50I/CMS50H
  (protocol B, OSCAR's `cms50f37_loader`) speak protocols different from the PO-400's (C).
  SpO2 Assistant 3.1.0.4 sends only C; the older 2.x spoke B (2014 serial capture). So the
  PO-250 is C if it works with a current SpO2 Assistant, but could be B with an old one.
  The PO-300 is open: its Auto + Manual modes point to C, a blog's PO-300 = CMS50E mapping to A.
- Scope (psytrap, 2026-10-29): fiedle400 supports the PO-400, PO-250 and PO-300 only; CMS50
  protocol-B support was on hold (T-105). Lifted for the PO-250 on 2026-11-04 (psytrap); built
  in v0.5.9.

## Execution Notes

<!-- Filled in on completion -->
