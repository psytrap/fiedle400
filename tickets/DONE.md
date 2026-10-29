# Completed Tickets

Archive register for `tickets/done/`, grouped by the ISO week (`%G-W%V`, Monday start) in which
each ticket was closed; the files live in `done/<ISO-year>-W<week>/`. See `README.md` for the
protocol. The second half is the project timeline before and around the tickets.

## Tickets by week

### 2026-W44 (Mon 2026-10-26 to Sun 2026-11-01)

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-084](done/2026-W44/T-084-download-checksum-failures-on-long-sessions.md) | Checksum-failed frames dropped silently on long session downloads, no retry | Local |
| [T-088](done/2026-W44/T-088-continuous-background-reader.md) | Evaluate a continuously-running background reader thread for the serial engine | Local |
| [T-089](done/2026-W44/T-089-finish-request-response-sequencing-cleanup.md) | Finish cleaning up request/response sequencing (remaining single-shot reads, erase status, flush/watermark race) | Local |
| [T-090](done/2026-W44/T-090-unify-flush-before-command-helper.md) | Unify the "flush stale reports" idiom into `_flush_before_command()` | Local |
| [T-092](done/2026-W44/T-092-clear-memory-no-early-return.md) | `clear_memory()` should not early-return when nothing matches the erase target | Local |
| [T-083](done/2026-W44/T-083-arduino-servo-test-fixture.md) | Arduino + servo mechanical test fixture for the PO-400 sensor | Local |
| [T-068](done/2026-W44/T-068-viewer-desaturation-event-legend.md) | Legend entry for desaturation/pulse event markers in the HTML viewer (Won't Do -- superseded by T-076) | Either |
| [T-081](done/2026-W44/T-081-group-backlog-tickets-by-ai-judgment.md) | Group backlog tickets by AI judgment | Either |
| [T-094](done/2026-W44/T-094-manual-mode-long-download-resume-budget-exhausted.md) | Manual-mode download of a long recording loses almost all samples -- resume budget exhausted | Local |
| [T-079](done/2026-W44/T-079-final-beta-testing-before-phase-2.md) | Final beta testing before Phase 2 (the minor version bump) | Local |
| [T-096](done/2026-W44/T-096-release-v0-5.md) | Ship the next release (v0.5.x) -- re-run the Runbook Checklist | Local |
| [T-098](done/2026-W44/T-098-identify-po250-po300-oem-model-and-software.md) | Identify the PO-250 / PO-300 hardware and their PC software | Either |
| [T-100](done/2026-W44/T-100-map-spo2exe-device-table-and-transports.md) | Map `SpO2.exe`'s device table and its serial path | Cloud |
| [T-099](done/2026-W44/T-099-read-other-vendor-oximetry-files.md) | Read the other vendor oximetry files (Won't Do -- psytrap: download from the device is the task) | Cloud |
| [T-104](done/2026-W44/T-104-detect-po250-po300-po400-for-wizard-and-info.md) | Detect PO-250 / PO-300 / PO-400 for the wizard and `info` | Either |
| [T-101](done/2026-W44/T-101-download-recordings-from-other-models.md) | Download stored recordings from PO-250/PO-300 (no live/realtime mode) | Either |
| [T-103](done/2026-W44/T-103-spo2-review-analysis-and-cms50-compatibility.md) | CMS50 family download compatibility matrix (SpO2 Review unavailable) | Either |

### 2026-W43 (Mon 2026-10-19 to Sun 2026-10-25)

| Ticket | Title | Owner |
| :---: | :--- | :---: |
| [T-001](done/2026-W43/T-001-adopt-ticket-strategy.md) | Adopt a ticket strategy to replace `handoff/` | Local |
| [T-002](done/2026-W43/T-002-code-review-standards.md) | Standing code-review checklist | Local |
| [T-003](done/2026-W43/T-003-worked-download-walkthrough.md) | Worked example -- one real download, start to finish | Local |
| [T-004](done/2026-W43/T-004-spo2-sentinel-sync.md) | Synchronize SpO2/Pulse sentinels in `.spo2` export | Local |
| [T-005](done/2026-W43/T-005-html-spo2-viewer.md) | HTML viewer for `.spo2` files, offered from the wizard | Cloud |
| [T-007](done/2026-W43/T-007-html-viewer-feature-evaluation.md) | Evaluate further features for the HTML `.spo2` viewer | Cloud |
| [T-008](done/2026-W43/T-008-html-viewer-adopted-features.md) | HTML viewer extras adopted from the T-007 evaluation | Cloud |
| [T-009](done/2026-W43/T-009-html-viewer-as-default-output.md) | Evaluate making the HTML viewer the default output | Cloud |
| [T-010](done/2026-W43/T-010-done-archive-by-iso-week.md) | Group `tickets/done/` by ISO week; project timeline in `DONE.md` | Local |
| [T-014](done/2026-W43/T-014-patch-sync-script.md) | Script to apply and generate the local/cloud sync patches | Local |
| [T-015](done/2026-W43/T-015-coordinator-compact-clear-rule-and-model-check.md) | Context-hygiene hint and model check as an advisory rule | Local |
| [T-017](done/2026-W43/T-017-desaturation-and-basal-spo2-definitions.md) | Research the vendor's desaturation-event and "Basal SpO2" definitions | Cloud |
| [T-018](done/2026-W43/T-018-desaturation-events-and-basal-spo2.md) | Show desaturation events, event index and Basal SpO2 in the HTML viewer | Cloud |
| [T-019](done/2026-W43/T-019-validate-desat-algorithm-in-spo2-assistant.md) | Validate the decoded desaturation algorithm in SpO2 Assistant | Local |
| [T-020](done/2026-W43/T-020-multi-session-spo2-export-loses-gaps.md) | Multi-session `.spo2` export silently discards the gap between sessions | Cloud |
| [T-011](done/2026-W43/T-011-spo2-assistant-interop-check.md) | Check `.spo2` export compatibility against the real SpO2 Assistant | Local |
| [T-016](done/2026-W43/T-016-html-viewer-deferred-features.md) | Add save-as-PNG and a smooth trend overlay to the HTML viewer | Cloud *(Won't Do)* |
| [T-022](done/2026-W43/T-022-viewer-multi-session-gap-false-event.md) | HTML viewer draws a false desaturation event across a multi-session gap | Cloud |
| [T-025](done/2026-W43/T-025-viewer-configurable-saturation-parameters.md) | Configurable desaturation analysis parameters in the viewer | Local |
| [T-026](done/2026-W43/T-026-viewer-html-design-and-format-feedback.md) | HTML viewer design and format feedback | Local |
| [T-006](done/2026-W43/T-006-remove-plot-command.md) | Remove `fiedle400 plot` once the HTML viewer supersedes it | Cloud |
| [T-012](done/2026-W43/T-012-make-html-the-default-download-output.md) | Make the HTML viewer the default download output | Cloud |
| [T-013](done/2026-W43/T-013-view-command-for-existing-recordings.md) | `fiedle400 view FILE` opens the HTML viewer for an existing recording | Cloud |
| [T-027](done/2026-W43/T-027-js-detection-logic-test-coverage.md) | Automated test coverage for the viewer's ported JS detection logic | Cloud |
| [T-029](done/2026-W43/T-029-pulse-rate-desaturation-decode.md) | Decode and validate the pulse-rate desaturation detector | Cloud |
| [T-031](done/2026-W43/T-031-basal-spo2-rule-confirmation.md) | Confirm the exact Basal SpO2 calculation rule | Cloud |
| [T-030](done/2026-W43/T-030-pulse-rate-desaturation-implementation.md) | Implement the pulse-rate desaturation detector | Cloud |
| [T-036](done/2026-W43/T-036-spo2-assistant-check-procedure.md) | Reusable procedure for confirming a decoded algorithm in SpO2 Assistant | Cloud |
| [T-033](done/2026-W43/T-033-migrate-wizard-to-tkinter.md) | Evaluate migrating the interactive wizard from a terminal TUI to tkinter | Cloud |
| [T-039](done/2026-W43/T-039-clarify-user-vs-session-concept.md) | Clarify "User" vs "Session" in the device protocol | Cloud |
| [T-042](done/2026-W43/T-042-manual-mode-download.md) | Download Manual-mode recordings | Cloud |
| [T-038](done/2026-W43/T-038-fiedle400-vs-spo2-assistant-erase-behavior.md) | fiedle400 and the vendor SpO2 Assistant differ on auto-erase after download | Either |
| [T-037](done/2026-W43/T-037-clear-command-undefined-behavior.md) | `fiedle400 clear` sends the vendor's erase commands | Either |
| [T-032](done/2026-W43/T-032-desaturation-algorithm-review.md) | Review the desaturation-event algorithm against the decoded spec | Local or Cloud |
| [T-044](done/2026-W43/T-044-viewer-artifact-and-time-below-discrepancies.md) | Viewer shows a different "artifact"/"time below" than it computes | Cloud |
| [T-034](done/2026-W43/T-034-repo-clean-up.md) | Repo clean-up -- basic pass (duplicate file, launcher wording, stale build artifacts) | Either |
| [T-052](done/2026-W43/T-052-findings-recheck-for-release.md) | Re-check findings T1-T8 against this release's hardware testing | Local |
| [T-055](done/2026-W43/T-055-demo-recording-in-windows-installer.md) | Ship a synthetic demo recording in the Windows installer | Local |
| [T-062](done/2026-W43/T-062-windows-test-failures-viewer-tmp-dir.md) | `TestViewerTmpDir` fails on real Windows -- tests mock the wrong thing | Local |
| [T-063](done/2026-W43/T-063-pyproject-hid-dependency-wrong-package.md) | `pyproject.toml` declares the wrong `hid`-family package | Local |
| [T-064](done/2026-W43/T-064-windows-installer-ux-fixes-from-manual-test.md) | Windows installer UX fixes found during manual install testing | Local |
| [T-051](done/2026-W43/T-051-manual-mode-remaining-protocol-questions.md) | Local inspection -- G7 visual confirmation and Manual-mode protocol questions | Local |
| [T-066](done/2026-W43/T-066-0xec-byte1-low-nibble.md) | Decode `0xEC` byte 1, bits 0..3 (third data series; `clear -s` sends the whole delete sequence) | Cloud |
| [T-075](done/2026-W43/T-075-auto-session-duration-reads-half-the-real-time.md) | Auto-mode session duration/record count reads ~half the real recording time (the count is seconds; T3 reversed) | Either |
| [T-047](done/2026-W43/T-047-release-v0-4.md) | Ship the next release (v0.4.x) -- re-run the Runbook Checklist | Local |
| [T-086](done/2026-W43/T-086-clean-up-desat-py.md) | Clean up `fiedle400/desat.py` | Either |
| [T-087](done/2026-W43/T-087-session-count-mismatch-device-vs-fiedle400.md) | Device's on-unit "51 Seg" display vs. `fiedle400 sessions` listing only 31 | Local |

Tickets closed before W44 all fall in W43, giving it one folder. The week of each was taken from
the commit that closed it (the commit subjects in the git reflog), not guessed; check with
`git log --follow --format=%ad --date=format:%G-W%V -- <path>` if in doubt.

## Project timeline, reconstructed from the git history

One-time digest of the 121 reflog entries from the first commit (2026-09-03) to 2026-10-20, in UTC.
It lists what each week did, not every commit; `CHANGELOG.md` stays the live record. Weeks without a
commit (W38, W39, W41) are left out. Built from commit subjects only, so it says what a commit
announced, not everything it touched.

### 2026-W36 (09-03 to 09-06): protocol library and first CLI
- Protocol library split into Commands and Parsers, with RTC set-time.
- Protocol and engine packages modularised; `PROTOCOL.md` made byte-accurate (storage command layout
  tables, MSB framing, 7-to-8 bit reassembly, delta-nibble envelope).
- CLI streamlined: download warmup removed, duration decoding fixed; interactive wizard added.

### 2026-W37 (09-07 to 09-11): drivers and packaging
- Packaging strategy documented, live sub-frame framing clarified, capture artifacts tracked.
- Two HID backends (hidraw and hid) with cross-platform packaging and USB descriptor handling;
  invented fallback values purged.

### 2026-W40 (09-30): recordings you can open
- Native `.SpO2` binary export, the first plotting tool and a better interactive CLI.

### 2026-W42 (10-15 to 10-17): the big week, 0.1.1 to 0.4.4
- **10-15, from testing to a release candidate.** Live tests made opt-in and serialised;
  plotting made an optional extra that fails gracefully; cloud/local division of labour and the
  `handoff/` briefs introduced. Windows bring-up (console encoding, hidapi bundled, installer with
  Inno Setup, remembered save folder, `--workdir`) and releases 0.1.1 to 0.1.3. Project renamed to
  fiedle400. Simulated hardware (`hwsim`) and a replay of a real device trace found findings T6 and
  T7; T1 to T7 fixed in one patch; `selftest` added; Linux `install.sh` and udev script; 0.2.0 opened;
  matplotlib bundled and the first alpha released. A real multi-window download confirmed T6's fix and
  G7 passed. Manual recording mode found, with its own protocol (0xA0/0xA2/0xA3/0xA7), and its
  delta-nibble decoding solved. 0.3.0 opened; the clean-audit brief written.
- **10-16, audit and polish.** Clean audit applied (patch 0014), `RELEASE_PLAN.md` split with the
  investigation history moved to `CHANGELOG.md`, docs review (0015). Wizard output-format prompt
  (0.3.8), README rewrite, Windows G5/G6 verified, promoted from alpha to beta (0.3.9), published asset
  audited, repository made public, 0.4.0 opened, wizard offers to open the plot and shows the project
  page (0.4.2).
- **10-17.** Uninstall documented for every Linux install type; the uninstaller asks about settings (0.4.4).

### 2026-W43 (10-19 to 10-20): tickets and the HTML viewer
- Ticket process adopted (T-001) in place of `handoff/`; review checklist and worked download example
  (T-002, T-003); `SPO2_FORMAT.md` checked against OSCAR's source (T-004, T-005 opened).
- HTML viewer for `.spo2` files implemented (T-005, v0.4.12), then upgraded with gridlines, tooltip,
  zoom and statistics; width fix for wide displays; fix for a snap browser install.
- Viewer feature evaluation against SpO2 Assistant's own strings and manual (T-007); channel switches,
  print and an adjustable time-below level (T-008, v0.4.18); HTML-as-default question settled (T-009,
  T-012); `.spo2` export keeps SpO2 and pulse sentinels in step (T-004, v0.4.19).
- This ticket's own housekeeping (T-010), the patch sync script (T-014) and the advisory rule (T-015).
- Vendor desaturation-event and Basal SpO2 definitions decoded from `SpO2.exe` and the manual,
  written up in `SPO2_FORMAT.md` §7 (T-017); probe recording script and its validation against the real program (T-019), events and
  report values in the HTML viewer (T-018, v0.4.20), multi-session `.spo2` export keeps the
  pause between sessions (T-020) and the viewer pads it the same way, so no false event across it
  (T-022, v0.4.22).
