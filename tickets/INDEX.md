# Open Tickets

Live list of everything in `tickets/open/`. See `README.md` for the
protocol; `DONE.md` for the archive.

| Ticket | Title | Owner | Status |
| :---: | :--- | :---: | :--- |
| [T-047](open/T-047-release-v0-4.md) | Ship the next release (v0.4.x) -- re-run the Runbook Checklist | Local | Open |
| [T-051](open/T-051-manual-mode-remaining-protocol-questions.md) | Local inspection -- G7 visual confirmation and Manual-mode protocol questions | Local | Open |

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
| [T-052](open/T-052-findings-recheck-for-release.md) | Re-check findings T1-T8 against this release's hardware testing | Local | Open (deferred) |

## Open questions

Questions waiting on a decision from psytrap or on a check only the local side can run, each
with its source. When one is answered, move the answer to the source ticket or doc and delete
the line here.

### Waiting on a local check (device or Windows)

- **`fiedle400 clear` on the device** and **Manual mode on the real device**: folded into
  [T-047](open/T-047-release-v0-4.md)'s G5/G6/G9 gates, not tracked separately any more.
- **Manual-mode sample timing, unknown bytes, and `0xEC` byte 1 bits 0..3**: now
  [T-051](open/T-051-manual-mode-remaining-protocol-questions.md), tracked alongside T-047,
  not deferred.
