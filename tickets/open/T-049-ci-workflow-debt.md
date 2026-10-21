# T-049: CI/release-workflow debt (Ubuntu 26, Actions Node 20 warnings, macOS Gatekeeper)

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `.github/workflows/tests.yml`
  - `.github/workflows/build-release.yml`

---

## Description & Context

Split out of [T-047](T-047-release-v0-4.md): three named items from
`RELEASE_PLAN.md` §3g, checked against the actual workflow files on
2026-10-21. None of them is treated as blocking the next release;
recorded here so they aren't lost.

1. **`ubuntu-latest` already means Ubuntu 26, as of two days ago.**
   `RELEASE_PLAN.md` flagged "`ubuntu-latest` moves to Ubuntu 26 on
   2026-10-19" as a notice to decide on, not yet acted on; that date has
   now passed. `tests.yml` and `build-release.yml` both still say
   `runner: ubuntu-latest` / `runs-on: ubuntu-latest` (unpinned) -- so the
   *next* push onto this is the first one to actually run on 26, not a
   future hypothetical. Decide: pin `ubuntu-24.04` in both workflows, or
   accept 26 and specifically check whether the PyInstaller Linux binary
   needs a newer glibc than target systems have (the concern
   `RELEASE_PLAN.md` raised but never checked -- the check itself is
   [T-050](T-050-ubuntu-lts-compat-check.md)).
2. **GitHub Actions Node 20 deprecation warnings -- status unknown, not
   fixed.** `tests.yml`/`build-release.yml` still pin only major versions
   (`actions/checkout@v4`, `actions/setup-python@v5`,
   `actions/upload-artifact@v4`, `actions/download-artifact@v4`,
   `softprops/action-gh-release@v2`), so whether the 8 warnings from the
   `v0.3.9` run still reproduce depends on which exact release each major
   tag resolves to today -- not re-checked since 2026-10-17. Check the
   next CI run's log; only pin to specific newer releases if the warnings
   still appear.
3. **macOS Gatekeeper/quarantine is still untested.**
   `build-release.yml`'s "Smoke Test the Built Binary" (the step before
   "Package Release Asset") runs the binary in the **same job that just
   built it**, so it never picks up the `com.apple.quarantine` extended
   attribute a real download triggers. No step anywhere downloads the
   packaged asset and runs it as fetched. Add one (after "Package Release
   Asset", or a separate job depending on the uploaded artifact) -- this
   is macOS's only gate (`RELEASE_PLAN.md` D2), so it's worth closing
   specifically rather than carrying it forward again.

---

## Criteria

- [ ] `ubuntu-latest`/Ubuntu 26 decision made and recorded (pin
      `ubuntu-24.04`, or accept 26 with the glibc question checked)
- [ ] A CI run's log checked for the Node 20 deprecation warnings; pin
      specific action versions only if they still appear
- [ ] A macOS Gatekeeper/quarantine step added (download the packaged
      asset and run it as fetched) and passing
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
