# T-107: Confirm archive/ has a backup outside the working folder

- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `archive/` (local only, ~346MB: SpO2.exe brute-force material, pcaps)

---

## Description & Context

Split off from [T-046](../done/2026-W45/T-046-repo-clean-up-deep-pass.md)
(repo clean-up deep pass), which closed out every other item on its
checklist. `archive/` is gitignored and exists only in this working
folder -- it is kept (not deleted or moved), but as of T-046's close
psytrap had not confirmed it is backed up anywhere else. Losing the
working folder would mean losing this material permanently.

---

## Criteria

- [ ] `archive/` backed up outside this working folder (external drive,
      cloud storage, or similar), or a decision recorded that the
      material isn't worth keeping after all
- [ ] Backup location recorded in Execution Notes

---

## Execution Notes

<!-- Filled in on completion -->
