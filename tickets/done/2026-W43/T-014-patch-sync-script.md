# T-014: Script to apply and generate the local/cloud sync patches

- **Status:** Done
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

- [x] One script handles both directions (apply and generate), or two
      clearly-paired scripts if that reads better -- implementer's
      call, but documented either way in `AGENTS.md`.
- [x] Apply direction: dry-run check before applying, preserves the
      original patch's authorship (via `git am`, not a hand-written
      commit), runs the full test suite before anything is left
      committed, and refuses (does not partially apply) on a failed
      dry-run or a red suite.
- [x] Generate direction: produces a patch numbered correctly from the
      actual existing files on disk, not a separately-tracked counter
      that could fall out of sync with them.
- [x] `AGENTS.md`'s "Delivery" section is corrected to describe the
      path patches actually use (root-level), and references the new
      script(s).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

**Found when this ticket was picked up:** `scripts/sync_patch.py` already existed locally,
uncommitted and without tests (written during the T-008/T-009 apply). This patch
takes that file as its base and finishes it; nothing was rewritten from scratch.

**`scripts/sync_patch.py`** (changes to the local draft):
- `apply` now refuses when tracked files have uncommitted changes, because its rollback after a red
  suite (`git reset --hard`) would otherwise discard them. Untracked files do not count.
- `apply` keeps a copy of a successful patch in the repo root (gitignored by `*.patch`). Reason: the
  cloud's numbering is ahead of this root (`0016` to `0021` were applied from elsewhere, so
  `generate` would have started at `0016` and collided with them).
- `generate` looks for numbers in the repo root, `changes/` and any `--dir`, and takes `--number N`
  as an override. It prints a reminder when it numbered from disk. The patch that delivers this
  script is 0022, so the first `generate` in this repo should use `--number 23` (or whatever the
  cloud announces); after that the copies kept by `apply` carry the numbering.
- The default `root` arguments are read at call time (they were fixed at import, which made the
  functions untestable).
- The ticket's "path mismatch" is settled as follows: the cloud keeps patches in its own `changes/`
  folder, locally they are plain files, usually in the repo root. `AGENTS.md` "Delivery" now says
  so and names both script commands.

**Tests:** `tests/test_sync_patch.py` (11 tests): numbering from root, `changes/` and extra directories,
slugging, zero padding, and against throwaway git repositories: apply keeps the patch author and a
copy, refuses on a failed dry-run, refuses with uncommitted tracked changes, rolls back to the
previous commit on a red suite; generate numbers from disk, honours `--number` and refuses to
overwrite. They need `git` (skipped when absent; present on the three CI runners) and no network.

**Not done:** no automatic push, and no cloud-side counterpart (the cloud has no git history of
this repo; it builds patches by hand against the files it has synced). No version bump: scripts, tests
and docs only.
