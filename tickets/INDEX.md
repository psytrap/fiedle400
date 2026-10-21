# Open Tickets

Live list of everything in `tickets/open/`. See `README.md` for the
protocol; `DONE.md` for the archive.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-032](open/T-032-desaturation-algorithm-review.md) | Review the desaturation-event algorithm against the decoded spec | Local or Cloud | Open |
| [T-034](open/T-034-repo-clean-up.md) | Repo clean-up (tracked leftovers and local clutter) | Either | Open |
| [T-037](open/T-037-clear-command-undefined-behavior.md) | `fiedle400 clear`'s per-session erase sequence is unverified against a real capture | Local | Open |
| [T-038](open/T-038-fiedle400-vs-spo2-assistant-erase-behavior.md) | fiedle400 and the vendor SpO2 Assistant differ on auto-erase after download | Either | Open |
| [T-041](open/T-041-key-sessions-by-user-and-entry.md) | Key stored recordings by user and entry, not entry alone | Cloud | Open |

## Backlog (deferred)

Open tickets parked until psytrap picks them up again.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-021](open/T-021-broader-spo2-assistant-decode-coverage.md) | Broader real SpO2 Assistant `.spo2` decode coverage | Local | Open (deferred) |
| [T-023](open/T-023-viewer-blocked-areas-and-exportable-settings.md) | Viewer area-exclusion selection | Cloud | Open (deferred) |
| [T-024](open/T-024-viewer-settings-export-and-adjustable-parameters.md) | Viewer export/save settings button | Cloud | Open (deferred) |
| [T-035](open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md) | Validate the decoded pulse-rate events and Basal SpO2 rule in SpO2 Assistant | Local | Open (deferred) |
| [T-040](open/T-040-tkinter-wizard.md) | tkinter wizard, with the terminal wizard as fallback | Cloud | Open (deferred) |

## Open questions

Questions waiting on a decision from psytrap or on a check only the local side can run, each
with its source. When one is answered, move the answer to the source ticket or doc and delete
the line here.

### Waiting on a decision (psytrap)

- **Erase default in the wizard:** keep today's `[Y/n]` or switch to No (the T-040 mockup's
  default). [T-040](open/T-040-tkinter-wizard.md), deferred.
- **Windows console window** behind the tkinter wizard: keep or hide. [T-040](open/T-040-tkinter-wizard.md).
- **Auto-erase after download:** SpO2 Assistant erases after saving by default (`9D 7F 7F 7F 7F`);
  should `fiedle400` offer the same, and with which default?
  [T-038](open/T-038-fiedle400-vs-spo2-assistant-erase-behavior.md).
- **`fiedle400 clear`:** replace its bytes (`0xAA`/`0xAB`/`0xAC`, matching nothing the vendor
  sends) with the vendor's `9D 7F` commands, or remove it.
  [T-037](open/T-037-clear-command-undefined-behavior.md).
- **Patch version in the commit message:** stamp `0.4.NN` in each patch's subject so a sync can
  tell at a glance which patch is applied (offered 2026-10-20, no answer yet).

### Waiting on a local check (device or Windows)

- **Delete one recording** (`9D 7F 02 <user> <entry>`) has never been captured. One SpO2 Assistant
  "Delete" run with `tests/capture_tools`. [T-037](open/T-037-clear-command-undefined-behavior.md),
  [`PROTOCOL.md`](../PROTOCOL.md) §3.13.
- **Does `fiedle400 clear` erase anything?** List the recordings before and after.
  [T-037](open/T-037-clear-command-undefined-behavior.md).
- **Second user:** can the PO-400 record for user 2 at all? The captures only show user 1.
  [T-041](open/T-041-key-sessions-by-user-and-entry.md), [`PROTOCOL.md`](../PROTOCOL.md) §3.2.
- **Manual mode on the real device (T-042):** `fiedle400 sessions` and `download` on a PO-400
  in Manual mode, compared with SpO2 Assistant's result for the same recording. Also whether a
  device in Auto mode with no recordings minds the `A0` header query (never sent to one).
  [T-042](done/2026-W43/T-042-manual-mode-download.md).
- **Manual-mode sample timing:** `fiedle400` reads one sample per second (the header count, as
  `SpO2.exe` does). A recording timed with a stopwatch would confirm it.
  [`PROTOCOL.md`](../PROTOCOL.md) §3.14.
- **Manual-mode unknown bytes:** subframe bytes 3..4 (`08 7E` SpO2, `04 7E` Pulse in the data
  subframe), `D0` bytes 8..9, and `D0` kinds 1 and 4 (only 0 seen). [`PROTOCOL.md`](../PROTOCOL.md) §3.14.
- **`0xEC` byte 1, bits 0..3:** `0` in every capture; `SpO2.exe` compares it with 1 to pick a
  download path. [`PROTOCOL.md`](../PROTOCOL.md) §3.2.
