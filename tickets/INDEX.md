# Open Tickets

Live list of everything in `tickets/open/`. See `README.md` for the
protocol; `DONE.md` for the archive.

| Ticket | Title | Owner |
| :---: | :--- | :---: |

## Backlog

Open tickets parked until psytrap picks them up again.

### Process & docs

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-059](open/T-059-funding-license-for-additional-devices.md) | A "coffee/beer" license + funding note -- money for additional test devices | Either |
| [T-107](open/T-107-archive-backup-confirmation.md) | Confirm `archive/` has a backup outside the working folder | Local |

### Small UX & data-model odds-and-ends

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-040](open/T-040-tkinter-wizard.md) | tkinter wizard, with the terminal wizard as fallback | Cloud |
| [T-041](open/T-041-key-sessions-by-user-and-entry.md) | Key stored recordings by user and entry, not entry alone | Cloud |
| [T-057](open/T-057-auto-filename-postfix-on-collision.md) | Automatic filename choice -- insert the postfix right away | Cloud |
| [T-054](open/T-054-readme-demo-screen-capture.md) | Add a demo screen capture to README.md | Local |
| [T-093](open/T-093-set-username-via-wizard.md) | Set a username via the wizard | Cloud |

### Other PO-x00 models (T-061)

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-061](open/T-061-po250-po300-download-recordings.md) | PO-250 / PO-300 support: download stored recordings from the device | Either |
| [T-102](open/T-102-po250-po300-owner-test-run.md) | A PO-250/PO-300 owner runs fiedle400 on their device | Local |
| [T-105](open/T-105-cms50f37-protocol-b-download.md) | PO-250 download (protocol B) | Cloud |
| [T-108](open/T-108-po300-bluetooth-support.md) | PO-300 Bluetooth support -- scope question for T-105's PO-250-only scoping | Either |

### HTML viewer features & architecture

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-023](open/T-023-viewer-blocked-areas-and-exportable-settings.md) | Viewer area-exclusion selection | Cloud |
| [T-024](open/T-024-viewer-settings-export-and-adjustable-parameters.md) | Viewer export/save settings button | Cloud |
| [T-045](open/T-045-pulse-max-time-and-sentinel-index-quirks.md) | Pulse row reads the wrong channel's max_time; a sentinel-index quirk is shared by both implementations | Cloud |
| [T-056](open/T-056-html-viewer-comment-field.md) | Comment field in the HTML viewer | Cloud |
| [T-058](open/T-058-html-viewer-username-display-and-edit.md) | Show and edit a username in the HTML viewer | Cloud |
| [T-060](open/T-060-reevaluate-spo2-viewer-architecture.md) | Re-evaluate `spo2_viewer.py`'s architecture | Either |
| [T-067](open/T-067-viewer-grey-out-no-signal-periods.md) | HTML viewer should grey out no-signal/probe-out periods on the chart | Either |
| [T-069](open/T-069-js-interactive-behavior-test-coverage.md) | Automated test coverage for the viewer's interactive JS behavior (chart zoom/pan, hover, toggles) | Either |
| [T-076](open/T-076-viewer-event-band-toggle.md) | Checkbox to toggle drawing desaturation/pulse-rate event bands in the HTML viewer | Either |

### Manual-mode & erase protocol

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-072](open/T-072-investigate-manual-mode-erase.md) | Investigate `fiedle400 clear` against a Manual-mode recording | Either |
| [T-073](open/T-073-validate-manual-erase-against-real-device.md) | Validate `fiedle400 clear`'s Manual-mode `A1`/`D1` erase against real hardware | Local |
| [T-074](open/T-074-auto-mode-single-session-erase-does-not-work.md) | `clear -s N` (single Auto-mode session) does not erase anything on real hardware | Either |
| [T-082](open/T-082-wizard-erase-reports-success-but-sessions-persist.md) | Wizard reports erase succeeded, but the session is still there afterward | Local |
| [T-085](open/T-085-clear-poll-timeout-retry.md) | `clear_memory` should poll with a timeout/retry, not a single immediate re-list | Local |

### SpO2 Assistant validation & decode coverage

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-021](open/T-021-broader-spo2-assistant-decode-coverage.md) | Broader real SpO2 Assistant `.spo2` decode coverage | Local |
| [T-035](open/T-035-validate-pulse-events-and-basal-spo2-in-spo2-assistant.md) | Validate the decoded pulse-rate events and Basal SpO2 rule in SpO2 Assistant | Local |
| [T-070](open/T-070-fresh-spo2-assistant-desat-rerun.md) | Fresh real SpO2 Assistant run of the desaturation-event probe | Local |

### Release / CI infra debt

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-048](open/T-048-pty-input-mocking-review.md) | Review whether the Windows CI job needs more than `builtins.input` mocking | Either |
| [T-053](open/T-053-document-windows-local-test-procedure.md) | Document the local Windows test-execution procedure | Local |

### Long end

Investigations/mysteries with no clear next action yet -- unresolved
protocol quirks, unconfirmed flakiness, or a design decision with options
laid out but nothing chosen.

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-071](open/T-071-manual-mode-remaining-byte-mysteries.md) | Manual-mode subframe bytes 3..4, `D0` bytes 8..9, and `D0` kinds 1/4 | Either |
| [T-078](open/T-078-transient-first-command-usb-hiccup.md) | First command after idle occasionally fails to find/reach the device, succeeds on retry | Either |
| [T-080](open/T-080-viewer-spo2-hr-histogram.md) | SpO2/HR histogram in the HTML viewer (parity with SpO2 Assistant) | Either |
| [T-091](open/T-091-synchronized-flush-watermark.md) | Make "flush before command" an actual synchronization point, not a racy snapshot | Local |

## Open questions

Questions waiting on a decision from psytrap or on a check only the local side can run, each
with its source. When one is answered, move the answer to the source ticket or doc and delete
the line here. Anything with real remaining work gets its own ticket instead of sitting here
as a loose bullet (2026-10-21).

(None open right now -- the last three were resolved or spun off into
[T-071](open/T-071-manual-mode-remaining-byte-mysteries.md).)
