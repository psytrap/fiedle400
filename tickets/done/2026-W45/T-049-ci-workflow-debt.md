# T-049: CI/release-workflow debt (Ubuntu 26, Actions Node 20 warnings, macOS Gatekeeper)

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
   [T-050](../done/2026-W45/T-050-ubuntu-lts-compat-check.md)).
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

- [x] `ubuntu-latest`/Ubuntu 26 decision made and recorded (pin
      `ubuntu-24.04`, or accept 26 with the glibc question checked)
- [x] A CI run's log checked for the Node 20 deprecation warnings; pin
      specific action versions only if they still appear
- [x] A macOS Gatekeeper/quarantine step added (download the packaged
      asset and run it as fetched) and passing
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

Done 2026-11-02 (cloud, patch 0039, v0.5.7; local, v0.5.8).

5. **macOS quarantine job, first run: green.** Local, manual `gh workflow run build-release.yml`
   on `34c964a` (after the Node 20 fix and its own regressions were sorted below): `quarantine-
   macos` passed -- quarantine attribute set, Gatekeeper's response recorded, then the README's
   `chmod +x` + `xattr -d com.apple.quarantine` steps confirmed to unblock it, `--version`
   matching and `--help` working ([run 41470763625](https://github.com/psytrap/fiedle400/actions/runs/41470763625)).
   The run's overall conclusion was still `failure` from an unrelated job
   (`linux-oldest-lts`/T-050 -- a CI-script `pipefail`/`SIGPIPE` bug, not a real finding; see
   T-050's notes), which does not affect this item.

4. **`tests.yml` on GitHub, re-checked after the Node 20 fix:** two CI regressions surfaced on
   the push that carried the version bump -- both pre-existing local fixes from this same
   session that had been left uncommitted (`tests/test_serial_emulator.py` still called
   `PulsoxHidDevice(dev_path=...)` after T-106 renamed the parameter; `scripts/
   wizard_gui_mockup.py` still had `self.fmt` after the test file's matching rename). Both
   committed and pushed; [run 41470535172](https://github.com/psytrap/fiedle400/actions/runs/41470535172)
   green on all three OSes, no Node 20 warning in the annotations.

1. **Ubuntu: decided, pinned.** psytrap, 2026-11-02: "22 LTS is minimum". `build-release.yml`'s
   Linux build now runs on `ubuntu-22.04` (glibc 2.35), the oldest supported release, so the
   shipped binary runs on 22.04 and everything newer. (Until 2026-10-19 `ubuntu-latest` was
   24.04, glibc 2.39, so earlier binaries likely did not start on 22.04 at all; T-050 adds the
   container check.) `tests.yml` stays on `ubuntu-latest`: it only runs the Python suite, and
   following the newest Ubuntu there is useful early warning. When GitHub retires its 22.04
   runner image, build in an `ubuntu:22.04` container instead.
2. **Node 20 warnings: checked, fixed.** Local, 2026-11-02: the annotations on the latest real
   run (`gh run view <id>`, not grep-able from the step logs -- they're separate annotation
   entries) name exactly two actions: `actions/checkout@v4` and `actions/setup-python@v5`.
   Confirmed each's `action.yml` at the next major (`checkout@v5`, `setup-python@v6`) declares
   `using: node24` directly, so both are bumped in `tests.yml` and `build-release.yml`.
   `upload-artifact`/`download-artifact@v4` and `action-gh-release@v2` were not named in the
   annotations, so left alone per this item's own caution against bumping blind.
3. **macOS quarantine: job added.** New job `quarantine-macos` (needs `build`; `release` now
   needs it too) downloads the packaged `fiedle400-macos-arm64`, sets
   `com.apple.quarantine` as a browser download would, records whether Gatekeeper lets it
   run (informational, bounded to 30 s), then follows the new README "Running on macOS"
   steps (`chmod +x`, `xattr -d com.apple.quarantine`) and requires `--version` to match and
   `--help` to work. The release notes name the same two commands. Not run yet: the first
   tag or manual run is the test.
