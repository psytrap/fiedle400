# T-001: Adopt a ticket strategy to replace `handoff/`

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `tickets/` (new)
  - `AGENTS.md`
  - `handoff/` (frozen, not deleted)

---

## Description & Context

psytrap asked to check `github.com/psytrap/refdiff`'s documentation
strategy and replace this project's `handoff/` convention with
whatever ticket strategy is used there, then write a ticket deciding
what to adopt and what not to, and execute it.

**What `handoff/` was:** loose `<topic>.md` request + `<topic>-response.md`
reply pairs in a git-tracked directory, used to brief the cloud on
investigations it can't run itself (no hardware access) and receive its
findings/patches back. No numbering, no status field, no criteria
checklist, no index of what's open vs. resolved -- you had to read
`RELEASE_PLAN.md`'s prose to know whether a given handoff was still
live.

**What RefDiff actually does** (`tickets/README.md` there, read in
full): a `tickets/open/` + `tickets/done/` directory of numbered
`T-NNN-slug.md` files, each with a `Status`/`Priority`/`Tier`/`Scope`
header, a `Description & Context` section, a `Criteria` checklist, and
an `Execution Notes` section filled in on completion; `INDEX.md` is a
live dashboard of open tickets, `DONE.md` an archive. Tickets move
`open/` -> `done/` via `git mv` on completion. Two things that don't
transfer: a "Ticket-Only by Default" golden rule (default action for
anything non-trivial is to *create a ticket and stop*, not do the
work, until someone explicitly says "execute ticket NNN"), and a
multi-subagent coordinator/dispatch protocol for sizing how many
subagents a ticket needs, plus a phase-based backlog
(Pre-Pilot/Tier-1/Tier-2/Tier-3/Upstream-Phases) tied to a MediaWiki
gadget's wiki-by-wiki rollout.

## Decision: what to adopt

- The directory shape (`open/`, `done/`, `INDEX.md`, `DONE.md`,
  `README.md`), the numbered-ticket convention, and the
  Status/Priority/Scope/Criteria/Execution-Notes template. This is a
  strict upgrade over `handoff/`'s loose pairs: one stateful file per
  work item instead of two files and no status at all.
- The `open/` -> `done/` move-on-completion pattern with index/archive
  dashboards -- the same idea already used this session to split
  `RELEASE_PLAN.md` (current status) from `CHANGELOG.md` (resolved
  history), now applied to discrete work items instead of narrative
  findings.
- A new field RefDiff has no equivalent of: **`Owner: Local | Cloud |
  Either`**. RefDiff is one contributor/agent working alone; this
  project's defining structural fact is the local-hardware /
  cloud-code split (`AGENTS.md`'s "Division of Labour" rule), so every
  ticket should say up front which side it belongs to.
- `AGENTS.md`'s existing "what a brief must carry" checklist (symptom
  + exact command + observed numbers, hardware facts, current repo
  state including uncommitted patches, an explicit statement of what
  is *not* yet known, safety constraints) -- folded into the ticket
  template's `Description & Context` guidance rather than dropped.

## Decision: what *not* to adopt, and why

- **"Ticket-Only by Default" golden rule.** RefDiff's rule is: for
  anything beyond a quick lookup, the default action is to *create a
  ticket and do nothing else* until explicitly told "execute ticket
  NNN". That is the opposite of how this project has actually run --
  psytrap gives direct instructions ("apply patch 14", "mark it
  unfixed", "do the wrapper") and expects them done in the same turn,
  not queued. Tickets here are for *tracking* a piece of work, not
  *gating* it.
- **Multi-subagent coordinator/dispatch protocol.** Sizes how many
  subagents a ticket needs and how they divide files. This project's
  delivery mechanism is two separate human-directed Claude sessions
  (local, cloud), not subagents spawned from one session to split a
  single ticket. Not applicable; dropped entirely.
- **Phase-based backlog (Pre-Pilot / Tier 1-3 / Upstream Phases).**
  Specific to RefDiff's wiki-gadget pilot rollout. This project
  already has its own structure for exactly this purpose --
  `RELEASE_PLAN.md` §3f (alpha vs. beta) and the G1-G8 gates -- so
  reusing RefDiff's tiers would just be a second, conflicting
  prioritization scheme. `Priority` (P0/High/Normal/Low) is kept since
  it's generic and useful on its own.
- **"Zero Deployment Automation Policy" (commit locally, never
  auto-push).** This project's actual convention, established and
  followed all session, is the opposite: test, bump, commit, *and
  push* after every applied change. Keeping that; not importing
  RefDiff's manual-release gate on top of it.

## Execution

1. Created `tickets/{README.md,INDEX.md,DONE.md}` and `tickets/{open,done}/`.
2. Wrote this ticket directly into `tickets/done/` (it documents and
   executes the decision in the same step, so there's no separate
   "open" phase for it).
3. Updated `AGENTS.md`: the "Rule: Delegation Path" section and the
   glossary's `handoff/` entry now point at `tickets/` instead.
   `handoff/`'s own content is left untouched and in place -- every
   existing `RELEASE_PLAN.md`/`CHANGELOG.md` citation into a specific
   `handoff/<topic>-response.md` file still resolves. A one-line
   `handoff/README.md` was added marking the directory frozen, with a
   pointer forward. Nothing in `handoff/` was migrated into ticket
   form retroactively: all eight existing request/response pairs are
   already resolved and cited by patch number elsewhere, so
   retrofitting them into the new template would cost real effort for
   no one left to read them that way.
4. `python3 -m unittest discover -s tests -t .`: 273 tests, OK
   (skipped=7) -- no code paths touched, docs-only change.

---

## Criteria

- [x] `tickets/` directory exists with the adapted protocol, README,
      INDEX, DONE, open/, done/.
- [x] `AGENTS.md` points new cloud-handoff work at `tickets/`, not
      `handoff/`.
- [x] `handoff/`'s existing files and every citation into them still
      resolve (nothing deleted or renamed).
- [x] Decision on what was and wasn't adopted is written down, with
      reasons specific to this project, not just copied from the
      source.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).
