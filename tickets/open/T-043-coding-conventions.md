# T-043: Write down coding conventions, starting with identifier names

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `.agents/rules/` (where the conventions file would sit, next to
    `code-review-standards.md`)
  - `fiedle400/desat.py` (`_detect` -- the concrete example below)
  - `AGENTS.md` (would need to point at the new rules file, as it does for
    `code-review-standards.md`)

---

## Description & Context

psytrap: abbreviated identifiers like `st` are not wanted in this code. There
is no coding-conventions document to point at today, so this ticket is to
write one -- naming first, since that is what prompted it.

`.agents/rules/code-review-standards.md` already covers naming *consistency*
("inconsistent naming for the same concept across files"), but nothing about
whether a name is legible in the first place. So a reviewer has no rule to
cite when a name is simply too short to read.

The concrete case: `fiedle400/desat.py`'s `_detect` uses `x` for the
normalized series, `st`/`en` for the open descent's start and end indices,
`v`/`p` for the current and previous sample, and `cur`/`n`/`c` for
candidates in the merge and acceptance steps. Reading the function requires
holding all of those in your head at once, which is what made the algorithm
hard to follow.

What is NOT decided:
- How far the rule goes. Loop counters (`i`) and comprehension variables are
  conventionally short and may be fine; the question is where the line sits.
- Whether the conventions cover anything beyond naming (line length, type
  hints, docstring shape, comment policy). AGENTS.md and
  `code-review-standards.md` already carry some of this, so the new file
  should not restate or contradict them -- part of this ticket is deciding
  what belongs where.
- Whether existing code gets renamed, and if so in what order. `desat.py` is
  the obvious first candidate, but renaming it touches product code, so it
  would be a cloud patch and its own ticket, not part of writing the
  conventions.

---

## Criteria

- [ ] A conventions file exists under `.agents/rules/`, with a naming rule
      that would have ruled out `st`/`en`/`v`/`p` and that states where the
      line sits for short names that stay acceptable.
- [ ] It says what it deliberately does not cover, and does not duplicate or
      contradict `AGENTS.md` or `code-review-standards.md`.
- [ ] `AGENTS.md` points at it, the way it points at
      `code-review-standards.md`.
- [ ] Any renaming of existing code is filed as its own follow-up ticket
      rather than done here.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
