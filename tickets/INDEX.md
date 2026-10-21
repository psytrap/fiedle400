# Open Tickets

Live list of everything in `tickets/open/`. See `README.md` for the
protocol; `DONE.md` for the archive.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-032](open/T-032-desaturation-algorithm-review.md) | Review the desaturation-event algorithm against the decoded spec | Local or Cloud | Open |
| [T-034](open/T-034-repo-clean-up.md) | Repo clean-up (tracked leftovers and local clutter) | Either | Open |

## Before next beta release

What must be done before the next beta. Proposed 2026-10-21; psytrap to confirm or change.

- [T-032](open/T-032-desaturation-algorithm-review.md): desaturation-event algorithm review.
- Local check: `fiedle400 clear` on the device (see "Open questions" below).
- Local check: manual mode on the real device (see "Open questions" below).

## Backlog (deferred)

Open tickets parked until psytrap picks them up again.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-021](open/T-021-broader-spo2-assistant-decode-coverage.md) | Broader real SpO2 Assistant `.spo2` decode coverage | Local | Open (deferred) |
| [T-023](open/T-023-viewer-blocked-areas-and-exportable-settings.md) | Viewer area-exclusion selection | Cloud | Open (deferred) |
| [T-024](open/T-024-viewer-settings-export-and-adjustable-parameters.md) | Viewer export/save settings button | Cloud | Open (deferred) |
| [T-035](open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md) | Validate the decoded pulse-rate events and Basal SpO2 rule in SpO2 Assistant | Local | Open (deferred) |
| [T-040](open/T-040-tkinter-wizard.md) | tkinter wizard, with the terminal wizard as fallback | Cloud | Open (deferred) |
| [T-041](open/T-041-key-sessions-by-user-and-entry.md) | Key stored recordings by user and entry, not entry alone | Cloud | Open (deferred) |

## Open questions

Questions waiting on a decision from psytrap or on a check only the local side can run, each
with its source. When one is answered, move the answer to the source ticket or doc and delete
the line here.

### Waiting on a decision (psytrap)

- **Windows console window** behind the tkinter wizard: keep or hide. [T-040](open/T-040-tkinter-wizard.md).

### Waiting on a local check (device or Windows)

- **`fiedle400 clear` on the device:** it now sends the vendor's `9D 7F` commands and reports
  whether the recordings are gone. Delete-all is confirmed by the vendor captures; delete-one
  (`clear -s N`, `9D 7F 02 <user> <entry>`) has never been captured. Throwaway recordings only.
  [T-037](done/2026-W43/T-037-clear-command-undefined-behavior.md), [`PROTOCOL.md`](../PROTOCOL.md) §3.13.
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
