# T-014: Script to apply and generate the local/cloud sync patches

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `scripts/` (new script, alongside the existing `bump_version.py`)
  - `AGENTS.md` ("Delivery" section -- documents the patch convention
    this script automates)
  - Root-level `NNNN-*.patch` files (gitignored, `*.patch` in
    `.gitignore`) and `AGENTS.md`'s stated `changes/NNNN-short-name.patch`
    path, which no delivered patch has actually used so far

---

## Description & Context

psytrap: the cloud/local patch handoff described in `AGENTS.md`
("Delivery") is currently done by hand every time (this session just
did it live for `0021-t008-t009-viewer-controls.patch`: dry-run check,
`git am`, run the full suite, report). Write a script that automates
both directions of that sync, not just the apply side.

**Direction 1, cloud -> local (apply):** given a patch file, do what
this session just did manually:
1. `git apply --check <patch>` first -- never apply blind.
2. If clean, apply it (`git am` to preserve the patch's own
   author/date/Subject/Co-Authored-By, matching how `0021` carried
   `Claude Sonnet 5.5`'s own attribution through -- a plain `git apply`
   plus a hand-written commit would lose that).
3. Run `python3 -m unittest discover -s tests -t .` and fail loudly
   (don't commit) if the suite doesn't come back clean.
4. Report: which patch, applied commit hash, test result summary --
   the same shape this session reported in chat, as actual output
   instead of narrated by hand each time.

**Direction 2, local -> cloud (generate):** psytrap explicitly asked
for this direction too, not just the apply side that already existed
informally. When local has committed work the cloud side should see
(a fix, a decision, new tickets -- e.g. this session's own
`e7b08f9` ticket commit), generate a `git format-patch`-style patch
file for it, numbered with the next free number in the existing
sequence (root-level `NNNN-short-name.patch`, continuing from `0021`
-- `ls *.patch` plus the gaps already visible between `0015` and
`0021` is the actual numbering source of truth, not a counter file
that could drift from it).

**A doc/practice mismatch found while scoping this, worth reconciling
here rather than leaving it to drift further:** `AGENTS.md`'s own
"Delivery" section says patches are delivered to `changes/NNNN-short-
name.patch`, but no `changes/` directory exists and every patch
actually delivered and applied this session (and `0005` through
`0015` before it) landed at the repo root instead. The script should
follow what's actually been practiced (root-level), and `AGENTS.md`
corrected to match reality rather than the unused path -- don't
silently pick one without updating the other.

---

## Criteria

- [ ] One script handles both directions (apply and generate), or two
      clearly-paired scripts if that reads better -- implementer's
      call, but documented either way in `AGENTS.md`.
- [ ] Apply direction: dry-run check before applying, preserves the
      original patch's authorship (via `git am`, not a hand-written
      commit), runs the full test suite before anything is left
      committed, and refuses (does not partially apply) on a failed
      dry-run or a red suite.
- [ ] Generate direction: produces a patch numbered correctly from the
      actual existing files on disk, not a separately-tracked counter
      that could fall out of sync with them.
- [ ] `AGENTS.md`'s "Delivery" section is corrected to describe the
      path patches actually use (root-level), and references the new
      script(s).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
