# po400: Test & Release Plan

> **Scope:** First tagged release of the `po400` CLI (GitHub Release with Linux, Windows and macOS binaries)
> **Cadence:** Two-Phase Version Bump (Patch Pre-Flight • Minor Post-Shipment), adapted from the RefDiff rollout plan
> **Baseline:** `0.1.1` (Phase 1 done; no git tags exist yet; `master` had 25 commits at `0ab3bf0`, before patches 0005+)
> **Status:** Strategy approved by psytrap (2026-10-15). All blockers B1–B7 are resolved: B1, B1b and B3 via patch 0001 (applied locally and tested on real hardware by psytrap, 2026-10-15), B2, B4, B5 and B6 via patch 0002, B7 locally. Binary and installer verified on a real Windows 8.1 machine with the device attached. Nothing has been tagged or released. The `fiedle400` rename (§3b) is pending.
> **Workflow:** Changes are made and unit/mock-tested in the cloud copy (`/mnt/project-files/po400`); psytrap applies the patches locally, runs the live gates (G5–G7) and pushes to the private remote `github.com/psytrap/fiedle400`, where CI (`tests.yml`) runs on every push and PR.

---

## 1. Version Strategy (Two-Phase Bump)

The bump strategy is taken from the RefDiff plan and adapted to a Python package:

| Phase | When | Command | Effect |
|:---|:---|:---|:---|
| **0. Reconcile** ✅ | Once, before the first release | `python3 scripts/bump_version.py set 0.1.0` | Done: both manifests now say `0.1.0` (`__init__.py` was `2.0.0`). |
| **1. Pre-Flight (Patch)** | Start of every release cycle, **exactly once** | `python3 scripts/bump_version.py patch` | `0.1.0 → 0.1.1`. This is the release candidate that gets tested, tagged and shipped. No feature bumps during pre-flight. |
| **2. Post-Shipment (Feature)** | Final step, **only after** pre-flight passed, the GitHub Release is verified live (§4 Ring 3), and the feature work has been reviewed by the user | `python3 scripts/bump_version.py minor` (or `major`) | `0.1.1 → 0.2.0`. Records the shipped milestone on `master`. The next cycle's pre-flight patch then produces `0.2.1`. |

**Rules**
- **Single source of truth.** The version lives in `pyproject.toml` (`[project].version`) and `po400/__init__.py` (`__version__`). `bump_version.py` rewrites both, and a test asserts they match (§2, G3).
- **One patch bump per cycle.** If pre-flight fails, fix forward on the same RC version. Don't bump again.
- **Small, focused diffs between bumps.** No monolithic changes; each blocker fix (§3) is its own commit.
- **Diff audit before every tag:** `git diff --stat v<prev>..HEAD && git diff v<prev>..HEAD`, which should show zero debris: no `output/` files, `.dump` or `.spo2` captures, `egg-info`, or `po400.zip`. For the first release, audit against the initial commit.

**`major` vs `minor`:** use `major` only for a breaking CLI change (renamed subcommands or flags, a changed default output format or location). Everything else uses `minor`.

---

## 2. Pre-Flight Quality Gates

All gates must pass on the patch-bumped RC before tagging.

```bash
python3 scripts/bump_version.py patch                      # Phase 1: once per cycle
git diff --stat && git diff                                # Diff audit: zero debris
python3 -m unittest discover -s tests -t . -v             # G1/G2: full mock suite
python3 -m po400 --version && python3 -m po400 --help      # G4: stdlib-only smoke test (no matplotlib)
pyinstaller po400.spec && ./dist/po400 --version && ./dist/po400 info   # G5: built binary must reach the device (local only)
PO400_LIVE=1 python3 -m unittest tests.test_device_live -v  # G6: live hardware, both backends (opt-in)
po400 download -o output/rc.spo2 && po400 plot output/rc.spo2   # G7: visual acknowledgment
```

| Gate | Check | Today |
|:---|:---|:---|
| **G1 Mock suite** | `python3 -m unittest discover tests`: 0 failures, 0 errors. The only skips allowed are the 7 opt-in live-device tests (plus the plot tests when matplotlib is absent); the count must not vary with device state. | ✅ 157 run / 7 skip (live device only) with matplotlib, after patches 0005–0007. |
| **G2 Capture regression** | `test_pcap_decoder` actually runs against `analysis/bum400_20260906_100516.pcap` (it must not skip). | ✅ Runs and passes (B2). |
| **G3 Version sync** | `tests/test_version.py`: `po400.__version__` equals `pyproject.toml` version; `po400 --version` prints it; bump script cycle works. | ✅ Passing. |
| **G4 Zero-dependency promise** | In a clean venv with no third-party packages, `python3 -m po400 --help`, `info`, `sessions` and `download` import and run. `plot` prints an install hint and exits 1. | ✅ Verified in a clean venv: 107 tests run, 0 failures (plot tests skip). |
| **G5 Binary build** *(local only)* | `pyinstaller po400.spec` succeeds, **and the built artifact runs a device-touching command** (`info`, then `sessions`) with a real PO-400 attached; for Windows, the installed binary from the installer. `--version`/`--help` alone are not enough: a binary that starts but cannot load the `hid` extension passes them (this happened before `0ab3bf0`). CI runners have no oximeter, so this gate can only run on psytrap's machines; CI only proves the build succeeds. | ✅ Binary and installer verified on Windows 8.1 (`info`, `sessions` on the live device). Re-run on each RC build. |
| **G6 Live hardware** *(mandatory, the analogue of RefDiff's live CDP invariant)* | `PO400_LIVE=1 python3 -m unittest tests.test_device_live` passes with a real PO-400 attached, on Linux with **both** backends (`hidraw` and `hid`); elsewhere with `hid` only (`hidraw` raises off Linux by design, and the Linux-only tests skip with a reason). Never run two live runs at once (a lock file serialises them). | ✅ Windows criterion passes (`po400 info` on a real 8.1 machine). Re-run the live suite on the RC: Linux both backends, Windows `hid` (needs patch 0006). |
| **G7 Visual & data acknowledgment** | Record a short session **with a finger on the probe**, download it to `.spo2`, `.csv` and `.json`, run `po400 plot`, and have the user confirm the PNG looks physiologically plausible. Per `.agents/rules/implausible_data_warning.md`, constant 95/64 or 99/95 values with probe-out flags fail this gate. | Manual. |
| **G8 Output location** | Per `AGENTS.md`, output goes to the current directory (or the configured workdir), never a hard-coded `output/`; help strings say the same. | ✅ The code always wrote to the cwd; only the help strings said `output/`. Fixed in `9647913`. |

---

## 3. Release Blockers (fix before Phase 1)

Each blocker is a small, separate commit, landed **before** the patch bump.

| ID | Problem | Evidence | Fix |
|:---|:---|:---|:---|
| **B1** ✅ | matplotlib is a hidden hard dependency | `po400/__init__.py:15` imports `plot` eagerly, so every `from po400 import ...` (including `cli.py:24`) pulls in matplotlib. `cli.py:42` already imports `plot` lazily, so the eager import defeats that. | Done: `plot_session` is resolved lazily via `__getattr__`; `plot = ["matplotlib"]` extra added; `po400 plot` prints an install hint when matplotlib is missing. |
| **B1b** ✅ | The release binary would crash on start | `.github/workflows/build-release.yml` installs only `pyinstaller hidapi`. Because of B1, the frozen binary would raise `ImportError` on every command (inferred, not yet built). | Fixed by B1. **Decision (psytrap): plot is not shipped in the binary.** `po400.spec` excludes matplotlib. **Graceful failure (psytrap):** every command now runs through `cli.run_guarded`, which turns unexpected errors into a one-line message and exit code 1 (Ctrl+C → 130); `PO400_DEBUG=1` shows the full traceback. |
| **B2** ✅ | The pcap regression test never runs | `tests/test_pcap_decoder.py` imports `capture.decode_pcap`, but the module is at `archive/capture/` (and `archive/` is git-ignored). | Done: decoders copied to `tests/capture_tools/` (tracked); the pcap fixture in `analysis/` was already tracked. This also fixes `test_export_spo2.py`, which imported `decode_spo2` from the git-ignored `archive/` and would have failed on a fresh clone or in CI. |
| **B2b** ✅ | The pcap decoder reads byte order backwards | `archive/capture/decode_pcap.py:73` treats a file starting with `d4 c3 b2 a1` as big-endian. It is little-endian, so 0 reports are parsed. | Done in `tests/capture_tools/decode_pcap.py` (274 reports, 244 samples); a test pins the little-endian case. |
| **B2c** ✅ | The test expects 2 sessions; the capture has 1 | After B2b: one `0xEC` frame, session 1, 243 records, 4m 03s. | The test was wrong: `analysis/bum400_20260906_100516.md` (frame 067) shows one `0xEC` header with 243 samples. The test now expects 1 session, id 1, 243 records. Open observation: the notes say 243 samples ≈ 122 s, while `duration_str` reports 4m 03s. |
| **B3** ✅ | Version drift and no `--version` | See G3. | Done: `scripts/bump_version.py` (`show`, `set`, `patch`, `minor`, `major`; refuses to bump when manifests disagree), `po400 --version`, `tests/test_version.py`. |
| **B4** ✅ | The release workflow doesn't test | `build-release.yml` builds on tag push with no test step. | Done: `test` job on ubuntu, windows and macos (Python 3.11) runs the suite stdlib-only (G4), then again with matplotlib (G1/G2); `build` has `needs: test`; on tag pushes the job fails unless `v<__version__>` equals the tag. |
| **B5** ✅ | Stale build metadata | `po400.spec` hidden imports omitted `po400.export`. | Spec hidden imports: `po400.export` added in 0001. (`po400.egg-info/` is untracked, so it was never an issue in git.) |
| **B6** ✅ | Docs point at a local machine | README, DESIGN.md and PROTOCOL.md used `file:///home/mik/...` links. | Done: all links are relative (README in 0002, the other two locally). |
| **B7** ✅ | Windows console encoding | Emoji and box characters raised `UnicodeEncodeError` on a legacy-codepage Windows console (cp850) (`handoff/windows-console-encoding.md`). | Fixed locally: output falls back to ASCII replacements instead of crashing. |

---

## 3b. TODO: rename the whole app to `fiedle400`

Decided by psytrap (2026-10-15). The GitHub repository is already
`psytrap/fiedle400`; the code, package and artifacts still say `po400`.

**Do this as its own change, not mixed into other work** -- it touches nearly
every file, so a rename commit interleaved with behaviour changes is unreviewable
and will conflict with any patch written against the old paths.

Surface area, so nothing is missed:

| Area | What changes |
|:---|:---|
| Package | `po400/` directory, and every `from po400 import ...` / `import po400` |
| Entry point | `[project.scripts]` in `pyproject.toml`, `prog="po400"` in `cli.py` |
| Version | `po400/__init__.py` `__version__`, `scripts/bump_version.py` manifest paths, `tests/test_version.py` |
| Tests | imports in every `tests/*.py`, plus `tests/capture_tools/` |
| Packaging | `po400.spec` (script path, `hiddenimports`, binary `name=`), `packaging/windows/po400.iss` (AppName, DefaultDirName, shortcut, context-menu keys, `OutputBaseFilename`) |
| CI | asset names and paths in `.github/workflows/build-release.yml` |
| Settings | `po400/config.py` `APP_NAME` -- note this moves the settings directory, so an existing `workdir` setting is silently abandoned unless migrated |
| Env vars | `PO400_LIVE`, `PO400_DEBUG`, and the planned `PO400_WORKDIR` |
| Docs | `README.md`, `DESIGN.md`, `PROTOCOL.md`, `PACKAGING.md`, `SPO2_FORMAT.md`, `AGENTS.md`, this file |
| Device rules | udev rule filenames `99-pulsox*.rules` (cosmetic; the VID/PID match is unaffected) |

Open questions to settle before starting:

- **Installed-name collision.** A user who installed `po400-setup.exe` keeps that
  install; `fiedle400-setup.exe` has a different `AppId` and installs alongside
  it. Decide whether the installer should detect and remove the old one.
- **Settings migration.** Either migrate `%APPDATA%\po400\config.json` to the new
  directory on first run, or accept that the prompt reappears once.
- **Timing vs the release.** Renaming after tagging `v0.1.1` keeps the first
  release coherent; renaming before it means the RC that was hardware-tested is
  not the one that ships.

---

## 4. Rollout Rings

### Ring 0: Local Release Candidate
1. Land B1–B7 as separate commits; G1–G4 pass locally.
2. **Phase 1:** `python3 scripts/bump_version.py patch` → `0.1.1`. Commit as `chore(release): v0.1.1`.
3. Diff audit (§1), then G5–G7 on the user's machine.
4. Tag: `git tag -a v0.1.1 -m "Release v0.1.1"`. The tag stays local until Ring 1.

### Ring 1: CI Build (dry run)
1. Run `build-release.yml` via **workflow_dispatch** on `master` (no tag, so the release job is skipped).
2. Download all three artifacts and smoke-test each on its own OS: `--version`, `--help`, `info` with the device attached (`info` now also prints the tool version and build). **This is the early-testing ring, the analogue of RefDiff's `common.js` harness.**

### Ring 2: Tagged GitHub Release
1. `git push origin v0.1.1`. The workflow builds and publishes the GitHub Release.
2. Release notes: what's new, udev rule, Windows `hid` note, checksums.

### Ring 3: Post-Shipment Verification & Feature Bump
1. **Live audit (the analogue of `check:deploy`):** download each published asset from the Release page, verify SHA-256 against the CI artifacts, and run `--version` to confirm it prints `0.1.1`.
2. **Phase 2 (final step):** only when Ring 3.1 passes and the user has reviewed the feature work: `python3 scripts/bump_version.py minor` → `0.2.0`, committed as `chore(release): open 0.2.0 after v0.1.1`. No tag; the next cycle's patch bump produces `0.2.1`.

---

## 5. Rollback

- **P0 (binary crashes, data corruption, `clear` erases unexpectedly):** mark the GitHub Release as pre-release or delete its assets; `git revert` the offending commit; ship a fix with a new patch RC (`0.1.2`). Never move or re-push an existing tag.
- **P1 (decode edge case, cosmetic):** fix forward in the next cycle. `download` is non-destructive, so users can re-download after updating.

---

## 6. Runbook Checklist

- [x] B1–B7 landed as separate commits; G1–G4 green locally (0001: B1, B1b, B3; 0002: B2, B4, B5, B6; B7 local)
- [x] Phase 1: `bump_version.py patch`, run **once** → `0.1.1`
- [ ] Diff audit: `git diff --stat && git diff`, zero debris
- [ ] G5: built binary runs `info` / `sessions` on the real device (local only; Windows 8.1 done once)
- [ ] G6: live device tests pass (Linux: `hidraw` and `hid`; Windows: `hid`)
- [ ] G7: real-finger session downloaded and plotted; user acknowledged the plot
- [ ] Ring 0: annotated tag `v0.1.1` created locally
- [ ] Ring 1: workflow_dispatch dry run; all 3 binaries smoke-tested on their OS
- [ ] Ring 2: push tag; GitHub Release published
- [ ] Ring 3: published assets verified (SHA-256, `--version` = 0.1.1)
- [ ] Phase 2 (final step, after user review): `bump_version.py minor` → `0.2.0`
