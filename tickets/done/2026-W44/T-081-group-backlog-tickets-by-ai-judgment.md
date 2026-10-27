# T-081: Group backlog tickets by AI judgment

- **Status:** Done
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `tickets/INDEX.md`

---

## Description & Context

The "Backlog (deferred)" table in `tickets/INDEX.md` has grown into a
long flat list (~30 tickets) with no structure beyond ticket number --
viewer features, CI/release debt, hardware-protocol unknowns, and
process/docs items are all interleaved. That makes it hard to see which
deferred tickets are related, or to pick up a themed batch of them
together.

Next step: have the AI read through the current backlog and group the
tickets into themes by its own judgment (e.g. "HTML viewer features",
"release/CI infra debt", "hardware protocol unknowns", "process &
docs"), then propose and apply that grouping to `INDEX.md` as labeled
sub-sections (or a `Theme` column) under "Backlog (deferred)". psytrap
reviews the grouping once applied and can reshuffle or rename groups.

## Criteria

- [x] AI proposes a grouping covering every ticket currently in the
      backlog table
- [x] `INDEX.md`'s backlog table restructured into the agreed groups
- [x] psytrap has reviewed the result
- [x] Tests pass (docs-only change, n/a)

## Execution Notes

**2026-10-27:** Proposed an initial 5-theme grouping in chat (viewer
features, hardware/protocol/engine reliability, release/CI infra debt,
process & docs, small UX odds-and-ends), then applied it to `INDEX.md`
iteratively per psytrap's own picks and corrections rather than all at
once: pulled out "Release / CI infra debt" and "Small UX & data-model
odds-and-ends" first, then moved T-053 into the CI group (it's about a
release gate, not general process docs), merged T-068 into T-076 as
redundant along the way, split T-058 into a viewer half and a wizard/UX
half (the UX half filed as new T-093 and added to the Small UX group),
pulled the HTML viewer group out of the remaining flat list, renamed a
proposed "Left open" section to "Long end" per psytrap and moved T-071/
T-078/T-080/T-091 there, then finished grouping everything left over into
"SpO2 Assistant validation & decode coverage," "Manual-mode & erase
protocol," and "Process & docs." `scripts/check_ticket_index.py` (written
during this same session, T-NNN n/a -- a standalone tooling addition) was
used throughout to confirm every open ticket stayed listed with no stale
or duplicate rows after each change. End state: every backlog ticket sits
in a themed section, no flat leftover bucket remains.
