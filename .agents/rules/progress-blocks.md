# Rule: Pending-Steps Checklist While Working on a Ticket

## Trigger
- Always active for every ticket, however small, while an agent (local or cloud) works on
  it, and for any other task with more than one step. Also part of the ticket lifecycle (`tickets/README.md`, step 2).

## Guidelines
1. Keep the pending-steps checklist (the agent's status panel the user sees while it
   works) current: a short header naming the task, then one line per step, prefixed
   `✓` (done), `✱` (in progress) or `○` (not started).
2. Set it when the work starts, and refresh it each time a step completes or a long step
   (tests, a build, a search) starts, so the current step is always visible.
3. Keep each line short. Do not post the same list as a chat reply; replies are for
   results, blockers and questions.
4. Before the reply that delivers the result, resolve every line to its real end state;
   nothing stays `✱` or `○` once the work is delivered.

Example:

```
Patch 0023 for T-017

✓ Synced against the device
✱ Writing SPO2_FORMAT.md §7
○ Build patch 0023
```

## Why
psytrap kept having to ask "progress?" while long tickets ran (2026-10-20). A current
checklist answers that without a question.
