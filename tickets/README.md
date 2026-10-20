# Ticket Protocol

Replaces the old `handoff/` convention (loose `<topic>.md` +
`<topic>-response.md` pairs, no status, no numbering). See
[T-001](done/2026-W43/T-001-adopt-ticket-strategy.md) for why, and what was
deliberately *not* carried over from the source this was adapted from
(`github.com/psytrap/refdiff`'s `tickets/`).

## Directory layout

```
tickets/
├── README.md    # this file
├── INDEX.md     # live list of open tickets
├── DONE.md      # archive register of completed tickets
├── open/        # active tickets: T-NNN-slug.md
└── done/        # completed tickets, one folder per ISO week: done/<ISO-year>-W<week>/
```

A ticket stays at the same filename for its whole life. It moves once, from
`open/` to `done/<ISO-year>-W<week>/` (the week it was closed, Monday-start ISO 8601,
`date +%G-W%V`), so a link into `done/` has to name that week folder.

## When to open a ticket

Not every request needs one. Quick lookups, direct instructions ("fix X",
"apply patch N", "bump the version"), and anything small enough to finish
in the same turn just get done — this project runs on direct instruction,
not a queue. Open a ticket when a request is a **discrete, nameable unit
of work that outlives the current conversation**: a cloud investigation
or fix delivered as a patch, a multi-step hardware finding still being
chased, or a decision (like this one) worth a permanent record. In other
words: a ticket is for *tracking* a piece of work, not *gating* it — if
you're told to do something, do it; open the ticket alongside the work
(or right after), not as a prerequisite to starting.

## Lifecycle

1. Create `tickets/open/T-NNN-<slug>.md` from the template below, and apply the model
   check in `.agents/rules/coordinator-and-model-checks.md` (one advisory line).
2. Do the work (local hardware, or write the brief and hand it to the
   cloud per the `Owner` field). For every ticket, keep the pending-steps
   checklist (the agent's status panel) current: one line per step, `✓` done, `✱` in progress, `○` not
   started. Set it when the work starts, refresh it whenever a step
   completes or a long step (tests, build, search) starts, and resolve every
   line to its real end state before the result is delivered.
3. Append an `## Execution Notes` section: what was actually done, test
   results, what was deliberately left out and why.
4. Check off every `Criteria` item that's actually met.
5. `git mv tickets/open/T-NNN-<slug>.md tickets/done/<ISO-year>-W<week>/T-NNN-<slug>.md`,
   set `Status: Done`, update `INDEX.md` (remove it) and `DONE.md` (add
   it under that week's heading).
6. Commit and push as usual (this project pushes after every applied
   change — no separate manual-release gate on top of that).

A ticket closed without doing the work (psytrap says to drop it, scope
moved on, superseded by something else) follows the same steps 3-6 but with
`Status: Won't Do` instead of `Done`, and Execution Notes giving the reason
in one or two lines rather than a result. It still moves to `done/` and
`DONE.md` — "closed" is the state being recorded, not "shipped". It is not
reopened; if the work becomes wanted again later, open a fresh ticket.

## Ticket template

```markdown
# T-NNN: <Descriptive Title>

- **Status:** Open | In Progress | Done | Won't Do
- **Priority:** P0 | High | Normal | Low
- **Owner:** Local | Cloud | Either
- **Scope & Relevant Files:**
  - `path/to/file.py`

---

## Description & Context

<Why this ticket exists. For a cloud handoff: the symptom with the exact
command and observed numbers, hardware facts and measurements taken
locally, current repo state (including applied-but-uncommitted patches),
an explicit statement of what is NOT yet known, and any safety
constraints (never erase device flash -- stored sessions are real data).>

---

## Criteria

- [ ] Criterion 1
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
```

## Numbering

Zero-padded 3-digit (`T-001`, `T-002`, ...), monotonically increasing,
never reused. Filename: `T-NNN-kebab-case-slug.md`.
