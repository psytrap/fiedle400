# T-007: Evaluate further features for the HTML `.spo2` viewer

- **Status:** Done
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - Whatever T-005 produces (the HTML viewer itself)
  - `archive/bruteforce/SpO2.exe` (gitignored, pre-existing local
    artifact -- for mining the vendor UI's own feature set and
    strings, same method `PROTOCOL.md`'s header already credits)

---

## Description & Context

psytrap: once T-005's HTML viewer exists, evaluate what further
features it's worth adding -- using the official **SpO2 Assistant**
Windows software as the reference point for what a oximetry-viewing
tool is expected to offer, not inventing requirements from scratch.

**Not a request to build these now.** This ticket exists to hold the
evaluation and resulting proposals for a later decision -- same shape
as T-004/T-005/T-006, open and waiting for explicit execution.

Concrete starting points for the evaluation, not a committed list:
- What does SpO2 Assistant's own UI show per-recording beyond a raw
  SpO2/pulse trace? (e.g. session statistics -- min/max/average SpO2,
  time below a threshold, desaturation events -- the kind of summary
  a sleep-study-adjacent tool like OSCAR also computes, per the T-004
  cross-check this session.)
- Zoom/pan on the trace, since a long recording (the real 937-record
  ~15.5-minute session already captured) is hard to read as one flat
  line at full width.
- Export/print from the viewer itself, or is "already have the raw
  `.spo2`/`.csv`/`.json`" enough?
- Does the vendor UI distinguish or annotate finger-out stretches
  visually (relevant given T1's still-open finger-out path) -- if so,
  that's a feature worth matching once real finger-out data exists to
  test it against.
- Multi-session comparison, or is one recording at a time the right
  scope (matches how `fiedle400 download`/`plot` work today -- one
  session or all sessions concatenated, not a side-by-side view)?

Mining `SpO2.exe`'s own strings/resources for its actual menu items
and labels (the same static-analysis method already used for the
Manual-mode protocol discovery, PROTOCOL.md §3.15) is the concrete way
to ground this rather than guessing at what "spo2 assistant docs as
reference" should mean.

**Added, 2026-10-19 (deferred from T-005):** T-005 settled on a
one-shot temp-file HTML approach -- generate, open, clean up after the
browser's had a chance to load it. If this viewer becomes a standing
feature (used often enough that users want to reopen a past recording
without re-running the wizard, bookmark it, or similar), that
mechanism itself should be re-evaluated as part of this ticket, not
patched piecemeal later: e.g. a persistent viewer directory instead of
a cleaned-up temp file, or a "recent recordings" list in the template.
Not a commitment to build any of that -- just where that reconsideration
belongs when it comes up.

---

## Criteria

- [x] A written evaluation exists (this ticket's own Execution Notes,
      or a follow-up doc) listing candidate features, each tied to a
      specific observation from SpO2 Assistant (a string, a UI
      element, a documented behavior) -- not generic chart-viewer
      wishlist items.
- [x] Each candidate feature is explicitly marked adopt / defer / skip
      with a one-line reason, mirroring how the RefDiff documentation
      evaluation (T-001/T-002/T-003) was done -- not a flat list with
      no judgment applied.
- [x] Adopted features get filed as their own follow-up ticket(s)
      rather than implemented inline here.

---

## Execution Notes

**Method and limits.** The vendor tool was not run. The evidence is the text inside
`archive/bruteforce/SpO2.exe` (SpO2 Assistant, PE32 GUI), read with
`strings -a -n 3` (ASCII) and `strings -a -n 3 -e l` (UTF-16LE): English UI
labels, dialog and menu identifiers, config keys and C++ class names. A label shows that a
feature exists, not how it works, so anything about *how* the vendor computes a value below
is marked as a hypothesis. The evaluation was written before T-005 landed and re-checked
against its viewer (`fiedle400/spo2_viewer.py`, v0.4.12): one canvas chart with SpO2 (0 to
100 %) and heart rate on two axes, lines broken where a value is missing, no channel switch,
zoom, statistics or print. Our own data is 1 Hz SpO2 and pulse only
(`SPO2_FORMAT.md` §1); the vendor tool also handles a third channel, PI.

| # | Candidate | What SpO2 Assistant has (string / class) | Verdict | Why |
|---|---|---|---|---|
| 1 | SpO2 and pulse trace, each channel switchable | `BTN_Spo2GraphEnable`, `BTN_PRGraphEnable`, `CStripChartDisplay` | **Adopt** | Both traces exist in the T-005 viewer; the per-channel switch is missing and cheap. T-006 depends on parity with `plot`. |
| 2 | Choose the time window / zoom and pan | `STATIC_TimeInterval` ("Time Interval"), "Strip Chart Report" (`MENU_StripChartReport`) | **Adopt** | The vendor shows the recording in fixed time windows. The 937-record session is hard to read in one width; a window selector covers that. Interactive zoom itself was not seen in the strings (hypothesis: it is our own need, not a vendor feature). |
| 3 | Summary numbers: min and average SpO2, average and low pulse, time below a level | `STR_MinimumSpo2` "Minimum SpO2(%)", `STR_AvgPR` "Avg. Pulse Rate(bpm)", `STR_LowPR`, `STR_TimeLessThan` "Time(min) <", `CSumReportDisplay` ("Summary Report") | **Adopt** | Plain arithmetic on the samples, no clinical definitions needed. Exclude sentinel records from every statistic. |
| 4 | Print | `PrintDlgW`, `MENU_Print`, "Print Preview", `PrintWorker` | **Adopt** | The browser's own print, with a print stylesheet; almost no code. |
| 5 | Desaturation events and index | "Desaturation Event: drop in SpO2 by at least ... for a minimum duration of ... seconds" (`STR_Spo2EventChange`, `STR_LeastDuration`), "Total Event", "Index(1/hr)", "Adjusted Index(1/hr)", "Artifact(%)", `STATIC_DesaturationCriteriaLevel` (1 to 96) | **Defer** | The vendor's detection algorithm (what counts as the baseline, how artifact is removed) is not in the strings and is a hypothesis if we guess it. It is also a diagnostic-looking number from a hobby tool. If wanted, file a ticket with an explicit written definition and a "not a medical device" line. |
| 6 | "Basal SpO2" | `STR_BasalSpo2` | **Defer** | Meaning not stated anywhere we can see; do not copy the label without a definition. |
| 7 | Distribution tables (%SpO2 level, events, below %, time %) | `STR_SetSpo2Distribution`, `STR_DistributionRange`, `STR_Spo2Level`, `STR_BelowPercent`, `STR_TimePercent`, `MENU_DistributionRangeSet` | **Defer** | Mostly useful for long overnight recordings; item 3's time-below-level covers the short sessions we have. Revisit with a long real recording. |
| 8 | Alarm limits as lines on the chart | `Max SpO2`, `Min SpO2`, `Max Pulse`, `Min Pulse`, `Enable SpO2`, `CDlgAlarmSetting` | **Defer** | In the vendor tool these drive live alarms. Optional threshold lines are fine but not needed for a first version. |
| 9 | Mark finger-out stretches | "Artifact(%)" column in the report; no string that says how a stretch is drawn | **Defer** | No real finger-out recording exists (T1). Separate and mandatory for T-005 itself: **never plot 127 / 255 as readings** (`SPO2_FORMAT.md` sentinels; same risk as T-004 for OSCAR). Shading the gap waits for real data. |
| 10 | Smooth trend | `BTN_SmoothTrend` | **Defer** | Smoothing can hide short drops; if added, off by default and labelled. |
| 11 | Save the chart as an image | `BTN_TypeJpeg` (export type JPEG) | **Defer** | Browsers can already save a screenshot; revisit if asked. |
| 12 | Export formats from the viewer | `BTN_TypeCSV`, `BTN_TypePdf`, `BTN_TypeSpo2`, `BTN_TypeXML`; CSV header `DATE,TIME,SPO2,PULSE[,PI]` | **Skip** | `fiedle400` already writes spo2, csv and json; PDF comes from print (item 4). |
| 13 | Several recordings together | `MENU_JointReviewData`; the repo's own vendor capture is named `..._joint.SpO2` (`archive/capture/`) | **Skip** side by side | "Joint" in the vendor tool means one combined recording, which is what `fiedle400 download` of several sessions already produces. |
| 14 | Hide or exclude part of the data | `MENU_ExcludeData`, `BTN_UndoCurrent`, `BTN_UndoAll` | **Skip** | A viewer that edits what it shows is the wrong default for medical-looking data. |
| 15 | Patient info, report title, signature, e-mail the report | `CDlgUserInfo`, `CDlgReportTitle`, `CDlgSignature`, `CDlgSetEmail`, `FromEmailpassword`, `ProxyPassword` | **Skip** | Personal data and credentials; far outside a local file viewer. |
| 16 | Live view, pulse sound, alarm sound | `MENU_ReceiveRealData`, `Pulse Sound`, `BTN_AlarmSound` | **Skip** | The viewer reads files; `fiedle400` has no live view (T-005 scope). |
| 17 | PI (perfusion index) channel | `Max PI`, `Min PI`, `BTN_PIGraphEnable` | **Skip** | Our `.spo2` data carries no PI. |
| 18 | Colour scheme, language, units | `CDlgChooseColorScheme`, `MENU_SelectLang`, `CDlgUnitSet` | **Skip** | Use the browser's light/dark setting; English only like the CLI; no height/weight shown. |
| 19 | Reopen a past recording later (persistent viewer file or "recent recordings" list instead of T-005's cleaned-up temp file; added to this ticket from T-005) | `MENU_OpenFile` "Open File", "Recent File" (the vendor reviews saved `.SpO2` files and keeps a recent-files list) | **Defer** | No one has asked to reopen a recording yet, and the saved `.spo2` file is still there. Revisit if the viewer is used often; a `fiedle400 view FILE` command would be the smallest step, not a persistent directory. |

**Result.** Adopted items 1 to 4 are filed as **T-008**, which can start now that T-005 is
done. Items 5 to 11 and 19 stay deferred with the reason above; nothing deferred was
implemented here. Item 9's "do not plot sentinels" is a precondition in T-008: the T-005
viewer already breaks a line at a missing value, but a sentinel that reaches it as a number
(127 or 255) would still be drawn. No code changed (docs and tickets only), so there is no
version bump; the test suite was not touched.
