# Rule: Progress Blocks While Working on a Ticket

## Trigger
- Always active while an agent (local or cloud) works on a ticket, or on any task with
  more than one step. Also part of the ticket lifecycle (`tickets/README.md`, step 2).

## Guidelines
1. Show a progress block in the conversation the user reads, not only in a hidden status
   panel: one line per step, prefixed `✓` (done), `✱` (in progress) or `○` (next).
2. Post it when the work starts, and again each time a step completes or a long step
   (tests, a build, a search) starts, so the current step is always visible.
3. Keep each line short; the step that just finished may be bold.
4. The last block before the result resolves every line to its real end state; nothing
   stays `✱` once the work is delivered.

Example:

```
✓ Synced against the device
✱ Writing SPO2_FORMAT.md §7
○ Build patch 0023
```

## Why
psytrap kept having to ask "progress?" while long tickets ran (2026-10-20). A visible
block answers that without a question.
