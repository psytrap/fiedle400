# Rule: Context Hygiene and Model Check (advisory)

## Trigger
- One agent session works through several tickets in a row (for example "execute T-008 and
  T-009", then more), or a new ticket is being created.
- Applies to local and cloud sessions alike. Today this project runs short batches, not a
  15-20 ticket coordinator loop, so this is a light rule that scales up if that changes.

## What an agent can and cannot do
- `/clear`, `/compact` and switching the model are commands only the user can run. An agent
  never tries to run them. Everything below produces one advisory line at the end of an
  answer, nothing more.
- An agent cannot read its own context size. The rule therefore uses things it can
  observe: tickets finished in this session, a compaction summary having appeared, the
  same large file being re-read.

## Context: when to suggest `/clear` or `/compact`
- Do not suggest either between single tickets while subagent results stay short
  (about 200 tokens or less each; ask a subagent for one short paragraph).
- Suggest it once, at a clean break (a patch delivered, no ticket half done), when one of
  these is true:
  - about 10 tickets were finished in this session. This replaces the 15-20 ticket
    milestone of the original wording, because this project closes a handful of tickets
    per day, so 15-20 would never be reached before the context is long;
  - a compaction summary has already appeared once and work continues;
  - the agent notices it is re-reading files it already read.
  The original ~50k-token figure is kept as the intent (a long coordinator context) but is
  not used as a trigger, since it cannot be measured.
- The line to emit, verbatim:
  `>>> MEILENSTEIN KOMPLETT. Bitte führe '/clear' (für neuen Meilenstein) oder '/compact Behalte nur Liste der erledigten Tickets' aus. <<<`
- Before the user clears, the agent makes sure what a fresh session needs is in project
  memory or in the tickets (open questions, patch numbers still undelivered).

## Model check when a ticket is created
When opening a ticket (see `tickets/README.md`, Lifecycle step 1), compare the ticket with
the model the session is running on and, if they do not fit, say so in one line:
`Suggested model: <stronger|lighter> because <reason>.` The user decides; the agent never
switches itself.

Suggest a **stronger** model for:
- protocol or hardware findings, byte-level analysis, anything contradicting `PROTOCOL.md`;
- a design decision with several affected files, or work that gates a release;
- Priority P0/High, or a ticket whose scope the agent cannot state in two sentences.

Suggest a **lighter** model for:
- ticket bookkeeping, renumbering, link fixes, mechanical moves, doc typo passes;
- a change confined to one file with a clear definition of done.

No suggestion when the current model already fits. One line, once per ticket.
