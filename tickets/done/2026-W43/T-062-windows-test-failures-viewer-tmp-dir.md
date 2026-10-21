# T-062: `TestViewerTmpDir` fails on real Windows -- tests mock the wrong thing

- **Status:** Done
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `tests/test_cli_graceful.py` (`TestViewerTmpDir`)
  - `fiedle400/cli.py` (`_viewer_tmp_dir`, not believed to be buggy -- see below)

---

## Description & Context

Found 2026-10-21 running the full suite on a real Windows machine for the
first time this cycle (T-047's G1 Windows re-verification): 2 of 401 tests
fail, both in `TestViewerTmpDir`:

```
FAIL: test_resolves_to_the_saved_files_own_directory
  AssertionError: 'C:\\home\\testuser\\Documents\\fiedle400' != '/home/testuser/Documents/fiedle400'
FAIL: test_same_on_every_platform_no_special_casing_needed
  AssertionError: 'C:\\x\\y' != '/x/y'
```

Reproduced twice (full suite, then the class alone) -- deterministic, not
flaky.

**Root cause:** `_viewer_tmp_dir` (`fiedle400/cli.py:189-226`) calls
`os.path.dirname(os.path.abspath(saved_path))`. These two tests hardcode a
POSIX-style absolute path literal (`"/home/testuser/..."`, `"/x/y/rec.spo2"`)
and, for the "every platform" test, wrap the call in
`mock.patch.object(sys, "platform", plat)` to simulate Linux/win32/darwin.
That mock is **ineffective for this purpose**: `os.path` is bound to
`ntpath` or `posixpath` based on the real OS at Python startup, not
`sys.platform` at call time -- patching `sys.platform` never changes which
path module `os.path.abspath` actually runs. So on real Linux CI/dev
machines (`posixpath`), a POSIX literal round-trips unchanged and the test
passes by coincidence, not because the platform-independence claim in the
test's own docstring/name was ever actually exercised. On a real Windows
machine (`ntpath`), the same literal gets a drive letter prepended and
backslashes substituted -- which is exactly `ntpath.abspath`'s correct,
expected behavior for a drive-less absolute path, not a bug in
`_viewer_tmp_dir` itself.

**Likely also failing on CI's `windows-latest` job** (`tests.yml` already
runs the suite there, Python 3.11) -- not confirmed from this session (no
GitHub Actions access from here), worth checking directly when this is
picked up.

**Not a functional bug** as far as this ticket's evidence shows: a real
Windows run of `fiedle400` only ever passes `_viewer_tmp_dir` a real
Windows-native path (e.g. from `argparse`/the saved file's actual location,
always backslash-drive-letter form already), never a bare POSIX literal
like the test's. So the underlying feature likely works correctly on
Windows; only the test's literal expectations are platform-specific
without accounting for it.

---

## Criteria

- [x] Confirm against GitHub Actions whether `windows-latest` in `tests.yml`
      is currently failing this same way (if so, this is already a live CI
      gap, not just a local-session discovery)
- [x] Fix the two tests to assert OS-appropriate expected paths (e.g. build
      the expected path with `os.path.join`/`ntpath`/`posixpath` directly
      rather than a hardcoded separator style), or construct paths that are
      genuinely unambiguous on both path flavors
- [x] `test_same_on_every_platform_no_special_casing_needed`'s `sys.platform`
      mock either removed (since it doesn't actually test anything) or
      replaced with something that genuinely exercises multiple path
      styles (e.g. directly testing against both `ntpath` and `posixpath`
      modules, not relying on the real `os.path`)
- [x] Tests pass on both a real Linux and a real Windows machine
      (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21:** Rewrote both tests in `tests/test_cli_graceful.py`:
`test_resolves_to_the_saved_files_own_directory` now builds its input/
expected pair with `os.path.join`/`os.path.abspath` so it resolves
correctly under whichever real `os.path` the test actually runs under.
`test_same_on_every_platform_no_special_casing_needed` renamed to
`test_same_logic_on_posix_and_windows_path_styles` and rewritten to swap
`cli.os` for a `SimpleNamespace(path=posixpath/ntpath, getcwd=os.getcwd)`
in turn, genuinely exercising both path-module flavors regardless of the
real host OS -- the old `mock.patch.object(sys, "platform", plat)` never
did this (confirmed: `os.path`'s module binding depends on the real OS at
interpreter start, not `sys.platform`).

Verified against the real blocker: ran the class, then the full suite, on
the actual Windows machine (`192.168.2.165`, Python 3.11.9, Windows 8.1) --
both now pass (401 tests, `OK (skipped=81)`). Also re-ran the full suite on
Linux (401 tests, `OK (skipped=7)`) to confirm no regression there.

CI-confirmation criterion now checked via `gh`: `windows-latest` in
`tests.yml` has been failing with this exact assertion since commit
`1ce554e` ("Fix the HTML viewer failing to open on a real snap browser
install", 2026-10-19T10:52), already on `origin/master` -- run 39240567257,
job 118020088086, `gh api .../actions/jobs/.../logs` shows:
`AssertionError: 'D:\\home\\testuser\\Documents\\fiedle400' !=
'/home/testuser/Documents/fiedle400'` and `'D:\\x\\y' != '/x/y'` (note:
CI's Windows runner uses drive `D:`, this session's machine uses `C:` --
same root cause, different drive letter, confirming it's genuinely
OS-dependent and not specific to one machine). `fail-fast: true` cancelled
the ubuntu/macos jobs in the same run as a result, so this single test bug
has been blocking the *entire* CI matrix on every push since 2026-10-19,
not just Windows.

All criteria met. Closing.
