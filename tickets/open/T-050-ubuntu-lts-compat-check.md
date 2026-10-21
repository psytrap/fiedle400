# T-050: Check the Linux binary against an older Ubuntu LTS in CI

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `.github/workflows/build-release.yml` (the `linux` build leg,
    `runs-on: ubuntu-latest`)
  - `fiedle400.spec` (PyInstaller build)

---

## Description & Context

Related to [T-049](T-049-ci-workflow-debt.md) item 1, but a distinct,
concrete action rather than the pin-or-accept decision: PyInstaller links
the built binary against the **build machine's** glibc, and a binary built
on a newer Ubuntu can fail to run on an older one (`GLIBC_X.YY not found`)
-- glibc is forward-compatible, not backward-compatible. `RELEASE_PLAN.md`
raised this as a concern when `ubuntu-latest` was known to be moving to
Ubuntu 26 but never checked it; T-049 records the decision question, this
ticket is the check itself.

`build-release.yml` currently builds the Linux release asset on
`ubuntu-latest` alone, with nothing downstream verifying it runs anywhere
older. "Older LTS" here means whatever the project wants to promise
support for -- not yet decided; a reasonable floor to start from is
Ubuntu 22.04 (still in standard support), going lower only if psytrap
wants to support it.

What is NOT known:
- Which Ubuntu LTS versions this project actually wants to promise
  support for (README doesn't currently state a minimum, unlike D4's
  explicit Windows 8.1 floor).
- Whether the `hid`/`hidraw` backends or any other dependency have their
  own minimum-glibc or minimum-kernel requirements independent of
  PyInstaller's.

---

## Criteria

- [ ] A decision on the minimum Ubuntu LTS version to support, recorded
      (here or in `RELEASE_PLAN.md`/`README.md`, with a reason).
- [ ] A CI step or job added that runs the built Linux binary's
      `--version`/`--help` (at minimum) on that older LTS -- e.g. a
      container-based step (`ubuntu:22.04`) consuming the artifact built
      on `ubuntu-latest`, not a second from-source build.
- [ ] If the binary fails on the chosen floor, the fix (an older build
      image, `--target-glibc`-style build pinning, or similar) is scoped
      as its own follow-up rather than carried out inline here.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
