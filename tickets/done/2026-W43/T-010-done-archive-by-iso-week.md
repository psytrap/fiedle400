# T-010: Group `tickets/done/` by ISO week and reconstruct the project timeline in `DONE.md`

- **Status:** Done
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

- [x] `tickets/done/` is reorganized into `<ISO-year>-W<week>/`
      subfolders, moved with `git mv` (not delete+recreate) so
      `git log --follow` on every ticket still resolves back through
      its full history.
- [x] `DONE.md`'s ticket table is regrouped under one heading per ISO
      week, using each ticket's actual `done/` move date -- not
      invented or left ungrouped.
- [x] `DONE.md` gains a project-timeline section reconstructed from
      `git log`, grouped by the same ISO weeks, covering the project's
      full history (2026-09-03 onward) -- not just the weeks that
      happen to contain a ticket closure.
- [x] `tickets/README.md`'s documented layout and lifecycle step 5
      (`git mv tickets/open/... tickets/done/...`) are updated to
      show the week-subfolder destination path.
- [x] Every existing link into a `done/` ticket (from `INDEX.md`,
      other tickets, `RELEASE_PLAN.md`, etc.) is updated to the new
      path -- grep for `done/T-` across the repo before calling this
      done, not just the obvious files.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) --
      docs/tickets-only change, but confirm nothing references a
      ticket path from test fixtures.

---

## Execution Notes

**Done in the cloud copy** (the cloud has no `git log` for this repo, so the history work used
`.git/logs/HEAD`, the reflog, which lists every commit with its UTC time and subject).
- `tickets/done/` is now `tickets/done/2026-W43/`. The files are moved without content changes, except
  for the link fixes below, so git records them as renames and `git log --follow` should still resolve.
  Check that on your side after applying, since the cloud could not run it.
- Every ticket closed so far was closed in 2026-W43 (10-19 to 10-20), so there is exactly one folder.
  The close dates came from the closing commits' subjects, not from `git log --follow`.
- `DONE.md` has a heading per ISO week with the ticket table, and a project timeline for 2026-W36 to
  W43 built from the reflog (digest of what each week did, from commit subjects only).
- `tickets/README.md`: layout, the one-move rule and lifecycle step 5 name the week folder; step 1 now
  points at the model check from T-015.
- Links fixed: `README.md` (T-001), `AGENTS.md` (T-001), T-008 (to T-007, now the same folder),
  T-009 (two links to the open T-012, one level deeper), and T-012's link to T-009. Grep for `done/T-`
  and `](../` across `*.md` found nothing else; no test reads a ticket path.
- T-010 and T-014 and T-015 are closed by this same patch, so they moved into the new folder as well.

**Left out on purpose:** the `done/` week of T-010 itself is 2026-W43 because it is closed on 2026-10-20;
a different week for a later ticket will simply create a new folder.
