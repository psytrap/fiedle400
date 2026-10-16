# Handoff: documentation review (PROTOCOL.md / analysis/*.md)

Written by the local side for the cloud, 2026-10-16. Suggested model: **Opus,
high reasoning effort** — this is a line-by-line read of the densest, most
failure-sensitive docs in the repo, not a quick pass.

**Repo state:** HEAD `014bfcf`, version `0.3.6`, tests green. Since the
previous clean audit (patch 0014, `handoff/clean-audit-response.md`),
`RELEASE_PLAN.md` was split (resolved investigation history moved to
`CHANGELOG.md`, `f4005e4`) and T1 was marked unfixed with a new runtime
alert for its first real-hardware occurrence (`014bfcf`).

## The task

The clean-audit response explicitly flagged this as not done, deferred to a
separate patch if wanted:

> `PROTOCOL.md` and `analysis/*.md` were not re-audited line by line;
> Manual-mode sections (§3.14 and the German mirror) stay as they are. Say
> if you want a protocol-doc pass as a separate patch.

This handoff is that pass. Scope, in priority order:

1. **`PROTOCOL.md`** (769 lines) and **`analysis/po400_bytemap_reference.md`**
   (600 lines, the German mirror) — read both fully and cross-check them
   against each other. They're meant to describe the same byte-level
   protocol; flag any place they've drifted apart (added fact in one but
   not the other, contradicting values, a correction that only landed in
   one language).
2. **`analysis/bum400_20260906_100516.md`** (403 lines) and its paired
   `.pcap` — check whether the write-up's claims still match what's in
   `PROTOCOL.md` today; this is working notes from a capture session, not
   a maintained doc, so drift here is more likely than a bug.
3. Secondary, lower priority: a consistency pass over `DESIGN.md`,
   `README.md`, `SPO2_FORMAT.md`, `PACKAGING.md`, `RELEASE_PLAN.md`, and
   `CHANGELOG.md` — these were already rewritten/touched in patch 0014 and
   again this week (the `RELEASE_PLAN.md`/`CHANGELOG.md` split), so check
   mainly for stale cross-references between them (e.g. a `RELEASE_PLAN.md`
   section number or doc pointer that moved to `CHANGELOG.md` and wasn't
   updated everywhere it's cited) rather than re-reviewing them from
   scratch.

## What NOT to touch

Per `AGENTS.md`'s source-of-truth order: `PROTOCOL.md`'s Manual-mode
sections (§3.14 and the German mirror) are explicitly marked **unverified**.
This session's live-hardware work corrected large parts of both documents
against real device behaviour and a cross-checked relayed disassembly —
treat anything you find there as either already-resolved (check
`CHANGELOG.md` and the `§3.14.F` open-points note before assuming it's a
live bug) or a genuinely open question to flag, not a doc typo to silently
fix. Never state a protocol fact you haven't seen in a recording
(`tests/fixtures/*.trace.json`, `analysis/*.pcap`) or in these docs
yourself — mark anything you're inferring as a hypothesis.

## Suggested approach

Read-only, cross-file, no hardware involved — a cloud-side task per the
project's division of labour. Deliver findings as a patch (or a short list
of proposed patches, if the drift is substantial enough to want separate
review cycles) in `handoff/`, following the existing `docs-review-response.md`
naming convention this folder uses for paired briefs/responses. Do not apply
anything directly; psytrap reviews and applies per the existing process.
