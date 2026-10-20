# T-015: Coordinator `/compact`/`/clear` cadence rule, and a model check at ticket creation

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `AGENTS.md` (or a new `.agents/rules/*.md`, same style as the existing
    `code-review-standards.md` / `implausible_data_warning.md`)
  - `tickets/README.md` (ticket creation step, if the model check lands there)

---

## Description & Context

The user supplied this rule verbatim and asked for it to be analysed and
implemented (not just copied in as-is):

> ## 4. Wann `/compact` oder `/clear` im Coordinator?
> - Führe zwischen einzelnen Tickets KEIN `/clear` aus, solange die
>   Subagent-Returns kurz bleiben (<200 Tokens pro Ticket).
> - Erst wenn ein kompletter Meilenstein (z. B. 15–20 Tickets) abgeschlossen
>   ist oder der Coordinator-Kontext >50k Tokens erreicht, gib am Ende deiner
>   Antwort aus:
>   `>>> MEILENSTEIN KOMPLETT. Bitte führe '/clear' (für neuen Meilenstein)
>   oder '/compact Behalte nur Liste der erledigten Tickets' aus. <<<`

This project does not currently have a documented "coordinator" workflow
(one agent session driving many tickets end-to-end via subagents) — the
existing `tickets/README.md` lifecycle and `AGENTS.md` "Rule: Delegation
Path" describe single tickets opened one at a time, not a batch/coordinator
loop. Before wiring this rule in, it needs to be reconciled with:

- Whether this project actually runs a multi-ticket coordinator loop today,
  or whether this is a forward-looking rule for a future workflow.
- `/clear` and `/compact` are Claude Code slash commands, not something a
  ticket or `AGENTS.md` prose can invoke on the user's behalf — the rule as
  written is an instruction for an *agent's own output*, to prompt the human
  operator to run the command. That needs to be stated correctly (an agent
  cannot run `/clear`/`/compact` on itself in this harness; a terminal-dialog
  caveat elsewhere in this project's own session instructions already notes
  interactive-only slash commands are off-limits here — this rule produces
  an advisory message, nothing more).
- What actually counts as "Subagent-Return" and how its token size would be
  measured/estimated in practice (this project's subagents, if any, are
  invoked via the `Agent` tool `Explore`/`general-purpose`/etc. — there's no
  existing instrumentation reading agent-return token counts).
- Where "Coordinator-Kontext >50k Tokens" would be observed from, given this
  session has no API for an agent to introspect its own current context size
  mid-conversation.

The second ask — "add model check for ticket creation and suggest model
switching when suitable" — is a separate, related process rule: when a
ticket is opened, check whether the current model is appropriate for the
ticket's nature (e.g. a trivial doc fix vs. a protocol-analysis deep-dive)
and suggest switching if not. This also needs grounding in what's actually
observable: this session knows its own model ID (surfaced via the
system prompt, e.g. "You are powered by the model named ...") but has no
tool to switch models for itself — only the user (or the desktop app's
model picker) can do that, so this is an advisory suggestion, not an
automated switch.

---

## Criteria

- [ ] Decide where this rule lives: `AGENTS.md` (new "Rule: Coordinator
      /compact / /clear cadence" section) vs. a new `.agents/rules/*.md`
      file in the existing style, and say why.
- [ ] Rule is restated accurately for this harness: it tells the agent to
      *emit an advisory message* recommending `/clear` or `/compact` to the
      human operator under the stated thresholds (milestone of N tickets
      done, or an estimated/self-reported context size) — not to execute
      either command itself.
- [ ] Thresholds (sub-200-token subagent returns, 15-20 ticket milestone,
      ~50k token coordinator context) are carried over or explicitly
      adjusted for this project's actual ticket volume and subagent usage,
      with reasoning either way.
- [ ] Model-check rule added for ticket creation: a short checklist of what
      signals should prompt a model-switch suggestion (ticket priority,
      scope size, whether it's a hardware/protocol finding vs. a doc/ticket
      bookkeeping task), stated as a suggestion to the user, never a
      self-switch.
- [ ] Both rules cross-reference `tickets/README.md`'s "When to open a
      ticket" / lifecycle sections if they modify ticket-creation behaviour,
      so the two docs don't disagree.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`) — expected
      no code change, doc-only ticket, but confirm the suite is still green
      after the edit.

---

## Execution Notes

<!-- Filled in on completion -->
