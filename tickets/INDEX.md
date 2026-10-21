# Open Tickets

Live list of everything in `tickets/open/`. See `README.md` for the
protocol; `DONE.md` for the archive.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-047](open/T-047-release-v0-4.md) | Ship the next release (v0.4.x) -- re-run the Runbook Checklist | Local | Open |

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
| [T-043](open/T-043-coding-conventions.md) | Write down coding conventions, starting with identifier names | Either | Open (deferred) |
| [T-045](open/T-045-pulse-max-time-and-sentinel-index-quirks.md) | Pulse row reads the wrong channel's max_time; a sentinel-index quirk is shared by both implementations | Cloud | Open (deferred) |
| [T-046](open/T-046-repo-clean-up-deep-pass.md) | Repo clean-up -- deep pass (decisions needed) | Either | Open (deferred) |
| [T-048](open/T-048-pty-input-mocking-review.md) | Review whether the Windows CI job needs more than `builtins.input` mocking | Either | Open (deferred) |
| [T-049](open/T-049-ci-workflow-debt.md) | CI/release-workflow debt (Ubuntu 26, Actions Node 20 warnings, macOS Gatekeeper) | Either | Open (deferred) |
| [T-050](open/T-050-ubuntu-lts-compat-check.md) | Check the Linux binary against an older Ubuntu LTS in CI | Either | Open (deferred) |
| [T-059](open/T-059-funding-license-for-additional-devices.md) | A "coffee/beer" license + funding note -- money for additional test devices | Either | Open (deferred) |
| [T-060](open/T-060-reevaluate-spo2-viewer-architecture.md) | Re-evaluate `spo2_viewer.py`'s architecture | Either | Open (deferred) |
| [T-065](open/T-065-installer-english-only.md) | Installer should only offer English, not German | Either | Open (deferred) |
| [T-067](open/T-067-viewer-grey-out-no-signal-periods.md) | HTML viewer should grey out no-signal/probe-out periods on the chart | Either | Open (deferred) |
| [T-068](open/T-068-viewer-desaturation-event-legend.md) | Legend entry for desaturation/pulse event markers in the HTML viewer | Either | Open (deferred) |
| [T-061](open/T-061-po250-po300-support-via-spo2-analysis.md) | PO-250 / PO-300 support via `.spo2` analysis | Either | Open (deferred) |
| [T-053](open/T-053-document-windows-local-test-procedure.md) | Document the local Windows test-execution procedure | Local | Open (deferred) |
| [T-054](open/T-054-readme-demo-screen-capture.md) | Add a demo screen capture to README.md | Local | Open (deferred) |
| [T-056](open/T-056-html-viewer-comment-field.md) | Comment field in the HTML viewer | Cloud | Open (deferred) |
| [T-057](open/T-057-auto-filename-postfix-on-collision.md) | Automatic filename choice -- insert the postfix right away | Cloud | Open (deferred) |
| [T-058](open/T-058-username-wizard-and-html-editable.md) | Set a username via the wizard; show and edit it in the HTML viewer | Cloud | Open (deferred) |

## Open questions

Questions waiting on a decision from psytrap or on a check only the local side can run, each
with its source. When one is answered, move the answer to the source ticket or doc and delete
the line here.

### Waiting on a local check (device or Windows)

- **`fiedle400 clear` on the device** and **Manual mode on the real device**: folded into
  [T-047](open/T-047-release-v0-4.md)'s G5/G6/G9 gates, not tracked separately any more.
- **Manual-mode sample timing and unknown bytes**: resolved in
  [T-051](done/2026-W43/T-051-manual-mode-remaining-protocol-questions.md) (2026-10-21): timing
  confirmed via the device's own RTC; subframe bytes 3..4 and `D0` bytes 8..9 remain unknown
  (documented in `PROTOCOL.md` §3.14); `D0` kinds 1/4 never reproduced.
- **`0xEC` byte 1 bits 0..3**: decoded in
  [T-066](done/2026-W43/T-066-0xec-byte1-low-nibble.md) (a third data series; never seen on a PO-400).
