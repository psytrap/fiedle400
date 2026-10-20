# Completed Tickets

Archive register for `tickets/done/`, grouped by the ISO week (`%G-W%V`, Monday start) in which
each ticket was closed; the files live in `done/<ISO-year>-W<week>/`. See `README.md` for the
protocol. The second half is the project timeline before and around the tickets.

## Tickets by week

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

Every ticket closed so far falls in W43, so there is one folder. The week of each was taken from
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
  report values in the HTML viewer (T-018, v0.4.20).
