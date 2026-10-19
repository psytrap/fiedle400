# T-007: Evaluate further features for the HTML `.spo2` viewer

- **Status:** Open
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

---

## Criteria

- [ ] A written evaluation exists (this ticket's own Execution Notes,
      or a follow-up doc) listing candidate features, each tied to a
      specific observation from SpO2 Assistant (a string, a UI
      element, a documented behavior) -- not generic chart-viewer
      wishlist items.
- [ ] Each candidate feature is explicitly marked adopt / defer / skip
      with a one-line reason, mirroring how the RefDiff documentation
      evaluation (T-001/T-002/T-003) was done -- not a flat list with
      no judgment applied.
- [ ] Adopted features get filed as their own follow-up ticket(s)
      rather than implemented inline here.

---

## Execution Notes

<!-- Filled in on completion -->
