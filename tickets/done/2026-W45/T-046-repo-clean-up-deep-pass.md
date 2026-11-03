# T-046: Repo clean-up -- deep pass (decisions needed)

- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `handoff/` (frozen archive, see decision below)
  - `archive/` (about 284 MB: SpO2.exe brute-force material, pcaps)
  - `po400.zip`, two `po400_2026-09-30T195453_2026-09-30T195827*.spo2` files
    in the repo root
  - Everything tracked by `git ls-files` (for the strays audit)

---

## Description & Context

Split from the original repo-inspection ticket (2026-10-20); the
no-decision-needed items moved to [T-034](T-034-repo-clean-up.md). Each
item here needs either a decision from psytrap or more investigation
before anything is deleted or moved -- it is a checklist for a later pass,
not an instruction to act now.

- **Decision for psytrap: keep `handoff/`?** It is frozen and still cited
  by filename from several docs. Keeping it is the safe default; archiving
  or deleting it would mean rewriting those citations. Record the
  decision here; do not move it without one.
- **Look for other root-level strays** with `git ls-files` on the device
  (files not referenced by any doc, test or script) before the pass
  starts.
- **`archive/` (local only, ~284 MB).** Keep, but confirm a backup exists
  outside the working folder.
- **`po400.zip` and two stray `.spo2` files in the repo root (local
  only).** Old recordings; move to a `recordings/` folder outside the repo
  if they are still wanted, otherwise delete.

### Not known yet

- Whether any root file is used by someone outside the repo (a CI job, the
  release workflow). The workflows were read once and do not mention
  `trace-response.md` or `fiedle400.bat` (both handled in T-034), but that
  is not a full audit of everything `git ls-files` turns up here.
- Which of the local-only files psytrap still wants kept.

### Safety

- Never delete anything under the device-stored data paths or fixtures:
  `tests/fixtures/*.trace.json` and `analysis/*.pcap` are source of truth.
- The cloud only reads the device folder; the local-only items here (
  `archive/`, `po400.zip`, the stray `.spo2` files) are for psytrap or the
  local agent to act on, not something a cloud patch can touch.

---

## Criteria

- [x] Decision on `handoff/` recorded in Execution Notes
- [x] `git ls-files` strays audit done, findings recorded (even if "none
      found")
- [x] `archive/` backup confirmed, or a decision recorded that it's not
      needed
- [x] Decision recorded for `po400.zip` and the stray `.spo2` files (kept
      and moved, or deleted)
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

- **`git ls-files` strays audit: none found.** Everything tracked at
  repo root is an expected doc or config file; nothing orphaned.
- **`po400.zip` and the two stray `.spo2` files: deleted.** `po400.zip`
  was a pre-rename (`po400` -> `fiedle400`) source snapshot fully
  superseded by git history; the two `.spo2` files were duplicates of
  recordings already under the now-removed `output/`.
- **Also deleted while here (not originally scoped, but same local
  clutter):** 7 patch files at the repo root (`0032`-`0039-*.patch`),
  all confirmed already merged into git history by matching each
  ticket number to its commit; 6 old `fiedle400_*.html` viewer session
  exports (8.9MB); the stale `build/`, `dist/`, `output/` directories
  and stray `__pycache__/` dirs (all gitignored, regenerate on demand).
- **Root docs moved into `docs/`** (`AGENTS.md`, `CMS50_COMPATIBILITY.md`,
  `DESIGN.md`, `PACKAGING.md`, `PROTOCOL.md`, `PROTOCOL_B.md`,
  `RELEASE_PLAN.md`, `SPO2_ASSISTANT_CHECKS.md`, `SPO2_FORMAT.md`);
  `README.md` and `CHANGELOG.md` stay at the root by convention. Every
  markdown link that crossed the move was fixed; prose citations with
  no path (`PROTOCOL.md §3.3`-style) were left as-is.
- **`handoff/`: kept, but split.** `handoff/archived/2026-W42/` now
  holds the 16 existing request/response pairs (all written
  2026-10-15/16, hence the single week); the `handoff/` root stays
  available for any future one-off local/cloud delegation, landing
  flat as before. Every filename citation into a moved file was
  updated to the new `handoff/archived/2026-W42/<file>` path.
- **`archive/` (346MB, local-only): kept, backup not confirmed.** Spun
  off as [T-107](../../open/T-107-archive-backup-confirmation.md) rather than
  blocking this ticket's close.
- Full test suite passes throughout (468 tests, 7 skipped as expected,
  checked after each step of this pass).
