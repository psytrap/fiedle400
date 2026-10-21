# T-046: Repo clean-up -- deep pass (decisions needed)

- **Status:** Open (deferred; psytrap, 2026-10-21)
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

- [ ] Decision on `handoff/` recorded in Execution Notes
- [ ] `git ls-files` strays audit done, findings recorded (even if "none
      found")
- [ ] `archive/` backup confirmed, or a decision recorded that it's not
      needed
- [ ] Decision recorded for `po400.zip` and the stray `.spo2` files (kept
      and moved, or deleted)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
