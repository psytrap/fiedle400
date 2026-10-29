# T-101: Download stored recordings from PO-250/PO-300 (no live/realtime mode)

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Parent:** [T-061](T-061-po250-po300-download-recordings.md)
- **Depends on:** [T-104](T-104-detect-po250-po300-po400-for-wizard-and-info.md) (detection)
- **Scope & Relevant Files:**
  - `fiedle400/engine/`, `fiedle400/hid_driver.py`; a serial transport next to it if needed
  - `PROTOCOL.md` §5, `README.md`

---

## Description & Context

Scope set by psytrap (2026-10-29): "download recording from device is the task",
"no live recording", "Only download recordings". `sessions` and `download` (and
the wizard) for the stored recordings of these models; no live or realtime
streaming, no erase.

What T-098 and T-100 settled (`PROTOCOL.md` §5): SpO2 Assistant sends the
PO-400's command frames unchanged over HID and over USB-serial (115200 baud),
and picks devices only by USB ID. The PO-250 ships with SpO2 Assistant; the
PO-300 has the PO-400's Auto and Manual storage modes. So:
- **HID model** (`28E9:028A` or `0483:5751`): the existing engine, with the
  extra ID accepted. Probably little more than that.
- **USB-serial model** (`10C4:EA60`, `1CBE:0002`, `0483:5740`, or STM32/USB
  ports): a serial transport under the existing engine, same commands and
  parsers. The shipped binary stays zero-dependency, so no `pyserial`: `termios`
  on Linux/macOS, the Win32 COM API through `ctypes` on Windows.
- Where the model's replies differ (model string, `0xEF` capability bytes,
  memory layout), branch on the model string from T-104, not on the USB ID.

Only OSCAR's loaders describe a different (`7D 81`) protocol; they are the
fallback if a real device turns out not to answer SpO2 Assistant's commands.
OSCAR divides the CMS50F v3.7 session duration by 2 and the CMS50I's by 4
(`duration_divisor`); after T-075 do not copy that without evidence.

Without hardware this is mock-tested only; the first run on a real device is
the test (T-102).

## Criteria

- [ ] Transport for the model chosen from T-104's report (HID ID added, or serial transport)
- [ ] `sessions` and `download` for that model, read-only (no erase, no live mode)
- [ ] Mock tests built from `PROTOCOL.md`; `README.md` says "untested on real
      hardware" until an owner confirms
- [ ] Tests pass

## Execution Notes

<!-- Filled in on completion -->
