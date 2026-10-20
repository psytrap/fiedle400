# T-010: Group `tickets/done/` by ISO week and reconstruct the project timeline in `DONE.md`

- **Status:** Open
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `tickets/DONE.md`
  - `tickets/done/` (currently flat, becomes week subfolders)
  - `tickets/README.md` (the documented layout and the `open/` ->
    `done/` lifecycle step)

---

## Description & Context

psytrap: group completed tickets in `tickets/done/` by **ISO calendar
week**, both as subfolders on disk and as section headings in
`DONE.md`, and separately reconstruct the project's timeline from the
git commit history into `DONE.md` rather than leaving `DONE.md` as
just a flat ticket-title table.

Two distinct pieces, both into `DONE.md`:

1. **Ticket archive, regrouped by ISO week.** Today `tickets/done/` is
   flat (`T-001-...md`, `T-002-...md`, ...) and `DONE.md` is one flat
   table. Move completed tickets into `tickets/done/<ISO-year>-W<week>/`
   subfolders (e.g. `tickets/done/2026-W43/T-001-...md`) via `git mv`
   so history/`git log --follow` still resolves, and restructure
   `DONE.md`'s table under a heading per week instead of one flat list.
   **ISO week, not a naive one** -- `%G-%V` (ISO 8601 year-and-week,
   Monday-start, belongs-to-the-week-containing-the-first-Thursday
   rule), not `%Y-%U`/`%Y-%W` (US-style, Sunday/Monday-start but keyed
   to the calendar year, which disagrees with `%G` at year boundaries).
   `date -d ... +%G-W%V` / `git log --date=format:%G-W%V` already use
   the right rule; just need to apply it consistently.
   The completion week for each existing ticket is **not** written
   inside the ticket file anywhere today (no `Completed:` field) --
   use the date of the `git mv` into `done/` (`git log --follow
   --format=%ad --date=format:%G-W%V -- <path> | tail -1`, i.e. the
   earliest commit touching that path under its done/ name) as the
   source of truth, not a guess.
2. **Project timeline derived from git commits, not from tickets.**
   `DONE.md` today only lists the 5 *ticket* closures, which all
   happened to land in the same week (2026-W43) even though the
   project's actual commit history spans back to 2026-09-03
   (`git log`'s first commit) across several earlier ISO weeks
   (W36, W37, W40, W42, W43 -- checked via
   `git log --format=%ad --date=format:%G-W%V | sort | uniq -c`).
   Add a timeline section to `DONE.md`, grouped by the same ISO weeks,
   summarizing what happened each week from the commit log (not a
   mechanical dump of every commit message -- a readable digest, the
   same editorial judgment `CHANGELOG.md` already applies to raw
   history). This is a one-time reconstruction of the past, not a
   process to maintain commit-by-commit going forward (`CHANGELOG.md`
   already exists for that and should stay the live record; this is
   filling in `DONE.md`'s missing *historical* picture once).

---

## Criteria

- [ ] `tickets/done/` is reorganized into `<ISO-year>-W<week>/`
      subfolders, moved with `git mv` (not delete+recreate) so
      `git log --follow` on every ticket still resolves back through
      its full history.
- [ ] `DONE.md`'s ticket table is regrouped under one heading per ISO
      week, using each ticket's actual `done/` move date -- not
      invented or left ungrouped.
- [ ] `DONE.md` gains a project-timeline section reconstructed from
      `git log`, grouped by the same ISO weeks, covering the project's
      full history (2026-09-03 onward) -- not just the weeks that
      happen to contain a ticket closure.
- [ ] `tickets/README.md`'s documented layout and lifecycle step 5
      (`git mv tickets/open/... tickets/done/...`) are updated to
      show the week-subfolder destination path.
- [ ] Every existing link into a `done/` ticket (from `INDEX.md`,
      other tickets, `RELEASE_PLAN.md`, etc.) is updated to the new
      path -- grep for `done/T-` across the repo before calling this
      done, not just the obvious files.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      docs/tickets-only change, but confirm nothing references a
      ticket path from test fixtures.

---

## Execution Notes

<!-- Filled in on completion -->
