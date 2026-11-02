# T-050: Check the Linux binary against an older Ubuntu LTS in CI

- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `.github/workflows/build-release.yml` (the `linux` build leg,
    `runs-on: ubuntu-latest`)
  - `fiedle400.spec` (PyInstaller build)

---

## Description & Context

Related to [T-049](../../open/T-049-ci-workflow-debt.md) item 1, but a distinct,
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

- [x] A decision on the minimum Ubuntu LTS version to support, recorded
      (here or in `RELEASE_PLAN.md`/`README.md`, with a reason).
- [x] A CI step or job added that runs the built Linux binary's
      `--version`/`--help` (at minimum) on that older LTS -- e.g. a
      container-based step (`ubuntu:22.04`) consuming the artifact built
      on `ubuntu-latest`, not a second from-source build.
- [x] If the binary fails on the chosen floor, the fix (an older build
      image, `--target-glibc`-style build pinning, or similar) is scoped
      as its own follow-up rather than carried out inline here.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-11-02 (cloud, patch 0039, v0.5.7).

- **Minimum:** Ubuntu 22.04 LTS (psytrap, 2026-11-02: "22 LTS is minimum"), i.e. glibc 2.35.
  Recorded in README ("Running on Linux") and `PACKAGING.md`.
- **Build:** T-049 pins the Linux build to `ubuntu-22.04`, the oldest supported release, so the
  glibc floor is met by construction. That is the fix this ticket asked to scope; it was small
  enough to do in the same patch. Until 2026-10-19 the build ran on 24.04 (glibc 2.39), so
  earlier releases most likely did not start on 22.04.
- **Check:** new job `linux-oldest-lts` in `build-release.yml` (needs `build`; `release` needs
  it) downloads the packaged `fiedle400-linux-x64.tar.gz`, unpacks it in a clean
  `ubuntu:22.04` container and runs `--version`, `--help` and `config`. Not run yet: the next
  tag or manual "Run workflow" is the first run.
- **Not covered:** device access (hidraw, udev) on 22.04; that needs hardware. The kernel's
  hidraw interface has not changed in a way that matters here, and the serial backend uses only
  termios.

**First real run (local, 2026-11-02): failed, but not on compatibility.** `linux-oldest-lts`
failed with exit 141 before the binary ever ran -- a `bash -e -o pipefail` script abort on
`ldd --version | head -1`: `head` closes its end of the pipe after one line, `ldd` gets
`SIGPIPE` writing the rest, and `pipefail` turns that into the whole line's exit status. The
two lines before it (`PRETTY_NAME`, the `ldd` version string itself) printed fine, confirming
the container really is Ubuntu 22.04 / glibc 2.35 as intended -- a CI-script bug, not a
glibc/compatibility finding. Fixed: `|| true` on that one diagnostic line (it's informational,
not a check). Re-run needed to confirm `--version`/`--help`/`config` actually pass now.
