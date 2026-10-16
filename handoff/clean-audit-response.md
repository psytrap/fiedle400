# Clean audit: response (patch 0014)

Scope: code, docs, tests, release (RELEASE_PLAN 3e), at device HEAD d67d1fa. Kept small on
purpose: an open-source tool with a few hundred users, and the docs are the guardrails an AI
co-programmer works from. 255 tests pass (7 skipped), also with hostile environment variables.

## In the patch (no behaviour change)

**Code**
- Removed unused imports and locals (cli, export, parsers, detector, device) and f-strings without placeholders.
- Deleted dead code: `cli._discover_sessions_to_download`, `cli._download_single_session` (duplicated the engine), `HidapiBackend` alias.

**Tests**
- Unused imports and locals removed in 10 test files.
- **Environment dependence found and fixed:** the suite failed for a developer who has `PO400_WORKDIR`, `PO400_DEBUG` or `FIEDLE400_DEBUG` exported (4 tests: test_config, test_cli_graceful x2, test_hwsim_linux unplug). Same class of bug as the `command_selftest` CI incident, other direction. New helper `hwsim.scrub_env()`; `ConfigTestBase` and both `run_cli` helpers use it.
- Checked and fine: no test touches the real `/dev`, `/sys`, home or config; live tests are opt-in; results are the same under another HOME/XDG_CONFIG_HOME, TZ and LANG=C.

**Docs (the contract)**
- `AGENTS.md`: new "Project Contract" on top: source-of-truth order, commands, invariants (never erase flash, offsets/raw samples/finger-out, one-line failures, no new deps), test rules, patch workflow, definition of done, glossary. The existing division-of-labour rules are unchanged below it.
- `DESIGN.md`: rewritten (was a v2.0.0 document with a 17-test, single-file layout and wrong frame sizes): module map, download flow, tests, platform notes.
- `PACKAGING.md`: rewritten as how the artifacts are built (was "Design / Pre-POC" with udev `XXXX` TODOs).
- `README.md`: Python 3.11+, alpha status, `detect` example, macOS default backend, test command and doc links.
- `.agents/rules/implausible_data_warning.md`: probe-out is now the 127/255 sentinels (flags kept for stream devices).
- `RELEASE_PLAN.md`: stale baseline line, D3 closed (floor 3.11), 3e marked delivered.
- Removed the duplicate root `ci-mock-hardware-response.md` (identical to the one in `handoff/`).

## Not in the patch: your call (all optional)

1. ~~**Bug: `download --timeout` is dead.**~~ Fixed in patch 0015 (it now caps the download). Original finding: It sets `duration_sec`, but the target record count comes from `record_count` first. Either remove the flag or make it cap the download. Needs a behaviour decision.
2. `-a/--all` is redundant with the default.
3. `download_session` has near-identical SpO2 and pulse loops; `main()` repeats `-d/-v/-b` on every subparser (`parents=` would do). Cosmetic; leave unless touching it anyway.
4. ~~`MockHidDevice` lives in production~~ Removed in patch 0015. Original finding: it lived in production `hid_driver.py` and `device.py` detects it by class name. Moving it to tests would be cleaner.
5. Used only by tests: `wait_for_eb_stream`, `buffer.peek`, `detect_and_decode`, some `Commands.*` builders, `Parsers.parse_eb_frames/parse_ed_frames/parse_stored_block`. Kept; delete if you want them gone.
6. **`pyproject.toml`**: author is "Developer", no license/URLs; the dependency is `hid` while CI and the binary use `hidapi` (different PyPI packages, both give `import hid`; the code handles both). No LICENSE, CHANGELOG or CONTRIBUTING file; a LICENSE matters most for an open-source tool.
7. **Repo settings** (cloud can't see them): confirm Actions default workflow permissions are read-only (the release job sets `contents: write` itself), and branch protection if wanted.
8. CI tests only Python 3.11 on three OSes, consistent with the 3.11 floor.

## Flagged, not touched
- `PROTOCOL.md` and `analysis/*.md` were not re-audited line by line; Manual-mode sections (§3.14 and the German mirror) stay as they are. Say if you want a protocol-doc pass as a separate patch.
- `fiedle400.spec` comment cites B1b correctly (matplotlib bundled; decision reversed in RELEASE_PLAN).
