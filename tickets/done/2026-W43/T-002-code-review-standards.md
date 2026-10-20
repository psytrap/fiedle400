# T-002: Standing code-review checklist

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `.agents/rules/code-review-standards.md` (new)
  - `AGENTS.md`

---

## Description & Context

From evaluating `github.com/psytrap/refdiff`'s documentation strategy
(psytrap, 2026-10-19): its `REVIEW_GUIDE.md` §2.5-2.6 has a reusable
clean-code / test-smell taxonomy and a "too much or too little test
coverage" proportionality check. po400 has run this kind of pass exactly
once (patch 0014, prompted by a one-off `RELEASE_PLAN.md` TODO) with no
fixed rubric -- the next pass would reinvent the criteria from scratch.
Everything else evaluated from RefDiff's doc set either already has a
po400 equivalent (findings register = T1-T8, diff-audit checklist =
`RELEASE_PLAN.md` §1, two-phase version strategy = already adopted) or
doesn't transfer (DOM-diffing-specific architecture, wiki-adoption
tiers, the ticket-first golden rule already rejected in T-001).

psytrap: "Do this."

---

## Criteria

- [x] `.agents/rules/code-review-standards.md` exists with a clean-code
      checklist, a test-smell checklist, and a coverage-proportionality
      check, each adapted to this project's actual tools (`unittest`,
      `pyflakes`), not copied verbatim from RefDiff's JS/ESLint wording.
- [x] States when to run it (not every commit) and who can (both local
      and cloud -- it's a rubric, not hardware-gated work).
- [x] `AGENTS.md` points at it from the existing "Definition of done" line.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Wrote `.agents/rules/code-review-standards.md` matching the existing
`.agents/rules/implausible_data_warning.md` format (Trigger +
Guidelines sections). Adapted RefDiff's clean-code/test-smell taxonomy
to this project's real tools and real incidents rather than copying
its wording: cited the T6 offset/page-naming confusion as the concrete
example of the "inconsistent naming" smell, and the T-001 stranded
`if __name__ == "__main__"` guard (commit `065785d`) as the concrete
example of "dead/unreachable test code" -- both real, already-fixed
bugs in this repo, not hypothetical categories. Explicitly noted what
was *not* duplicated (findings register, diff-audit checklist -- both
already have po400 equivalents) so the rule doesn't drift into
restating T-001's evaluation.

`AGENTS.md`'s "Definition of done" line now links to it.

Tests: 273 run, OK (skipped=7) -- docs-only change, no code touched.
