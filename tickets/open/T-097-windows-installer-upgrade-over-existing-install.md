# T-097: Verify the real Windows installer upgrades a pre-existing install cleanly

- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `packaging/windows/fiedle400.iss` (Inno Setup script -- `UsePreviousAppDir=no`,
    `[InstallDelete]` for the old `po400` folder, `uninsdeletekey` on the
    context-menu registry entries)
  - `.github/workflows/build-release.yml` (`fiedle400-setup.exe` build step)
  - [T-096](T-096-release-v0-5.md) (this cycle's release; the Windows
    install done during T-096 was a manual stand-in, see notes below)

---

## Description & Context

During [T-096](T-096-release-v0-5.md)'s Windows testing, the old
`fiedle400 0.4.38` install on `192.168.2.165` was replaced with the new
`0.5.0` build, but **not via the real Inno Setup installer**
(`fiedle400-setup.exe`) -- Inno Setup (`ISCC.exe`) isn't installed on
that machine, so the swap was done by hand: run the *old* install's own
registered uninstaller first, then manually copy the freshly-built
`dist\fiedle400.exe` into `%LOCALAPPDATA%\Programs\fiedle400\` and
recreate the Start Menu shortcuts with a small VBScript.

That confirms the end state works, but it does **not** exercise the
actual thing a real user does: run the new `fiedle400-setup.exe`
*on top of* an existing install, letting the installer itself handle
the upgrade. The `.iss` script has specific logic for this
(`UsePreviousAppDir=no` to relocate, `[InstallDelete]` to remove a
leftover pre-rename `po400` folder, `uninsdeletekey` to clean up old
context-menu registry entries) that has not been exercised this cycle,
and per the `.iss` comments was written for the earlier `po400` ->
`fiedle400` rename specifically -- it's not confirmed to still behave
correctly for a same-app version-to-version upgrade (e.g. does it
silently reuse the old install dir and overwrite in place, or does
something unexpected happen since `UsePreviousAppDir=no` normally
*moves* to a new default dir on every run).

## Criteria

- [x] Get Inno Setup (`ISCC.exe`) onto a Windows test machine (or build
      `fiedle400-setup.exe` via the existing `build-release.yml` CI job
      and download the artifact) so the real installer can be run, not
      a manual stand-in
- [x] With an existing `fiedle400` install present (any older version),
      run the new `fiedle400-setup.exe` over it and confirm: no leftover
      files/shortcuts/registry keys from the old version, the app
      launches and reports the new version afterward, and the user's
      recordings folder (`Documents\fiedle400`) and its demo recording
      are untouched
- [x] Separately confirm a **clean uninstall** first (run the old
      version's uninstaller, verify nothing is left behind -- files,
      Start Menu group, registry context-menu keys), *then* a fresh
      install of the new version, as a second, simpler path to compare
      against the in-place-upgrade path above
- [x] Note any divergence from what the manual T-096 swap already
      confirmed (if the real installer behaves differently, flag it)
- [ ] Clean up the portable `fiedle400-windows-x64.exe` test binary
      left on the Windows machine from this ticket's testing (and any
      left from T-096's Ring 1 smoke test) once done with it
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

CI part done 2026-11-02 (cloud, patch 0039, v0.5.7); first run confirmed green, local,
2026-11-02. Stays open only for criterion 5 (Windows test-machine cleanup).

- **New CI step** in `build-release.yml`'s `installer-windows` job, "Upgrade Test", before the
  existing fresh-install smoke test. It downloads the latest published release's
  `fiedle400-setup.exe`, installs it silently with the context-menu task, edits the user's
  `demo.SpO2` and adds a recording to `Documents\fiedle400`, then runs this build's installer
  over it. Checks: `--version` is the new one; the uninstall registry entry's `DisplayVersion`
  is the new one; one uninstaller, no other files in the program folder; the Start Menu group
  holds exactly its three shortcuts; both context-menu commands point at the installed exe; the
  edited demo and the recording are untouched. Then it uninstalls (waiting for the
  uninstaller, which re-launches itself from TEMP) and checks the program folder, Start Menu
  group, context-menu keys and uninstall entry are gone while the user's files stay. The
  existing step then covers "clean uninstall, then fresh install". This covers criteria 1 to 3
  with the real installer, on a CI runner rather than on 192.168.2.165.
- **Static finding (not changed):** `UsePreviousAppDir=no` (kept for the po400 rename)
  makes every upgrade install to the default `%LOCALAPPDATA%\Programs\fiedle400`. Same-folder
  upgrades, which is everyone on the default, overwrite in place. A user who picked a custom
  folder gets the new version in the default folder, the uninstall entry and shortcuts move
  there, and the old copy is orphaned. Rare, so documented in `PACKAGING.md` only.
- **First CI run: green.** Local, manual `gh workflow run build-release.yml` on `34c964a`
  (after the Node 20 fix and its own regressions were sorted; see T-049): `installer-windows`
  passed end to end, both the new "Upgrade Test" step and the existing fresh-install/uninstall
  smoke test ([run 41470763625](https://github.com/psytrap/fiedle400/actions/runs/41470763625)).
  No divergence from T-096's manual swap noted.
- **Left for local:** remove the portable test binaries from the Windows machine
  (`192.168.2.165`, criterion 5) -- needs hands-on access to that machine.
