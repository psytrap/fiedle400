# T-097: Verify the real Windows installer upgrades a pre-existing install cleanly

- **Status:** Open
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

- [ ] Get Inno Setup (`ISCC.exe`) onto a Windows test machine (or build
      `fiedle400-setup.exe` via the existing `build-release.yml` CI job
      and download the artifact) so the real installer can be run, not
      a manual stand-in
- [ ] With an existing `fiedle400` install present (any older version),
      run the new `fiedle400-setup.exe` over it and confirm: no leftover
      files/shortcuts/registry keys from the old version, the app
      launches and reports the new version afterward, and the user's
      recordings folder (`Documents\fiedle400`) and its demo recording
      are untouched
- [ ] Separately confirm a **clean uninstall** first (run the old
      version's uninstaller, verify nothing is left behind -- files,
      Start Menu group, registry context-menu keys), *then* a fresh
      install of the new version, as a second, simpler path to compare
      against the in-place-upgrade path above
- [ ] Note any divergence from what the manual T-096 swap already
      confirmed (if the real installer behaves differently, flag it)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

(Not started.)
