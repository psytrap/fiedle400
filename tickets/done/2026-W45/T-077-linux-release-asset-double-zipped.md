# T-077: Check why the Linux release asset is `tar.gz.zip`

- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `.github/workflows/build-release.yml` (`asset_name:
    fiedle400-linux-x64.tar.gz`, the `tar -C ... -czf` packaging step,
    the `actions/upload-artifact@v4` / `actions/download-artifact@v4`
    pair, and the `softprops/action-gh-release` `files:` glob)

---

## Description & Context

psytrap noticed the Linux asset ends up as `fiedle400-linux-x64.tar.gz.zip`
somewhere in the release flow, not the plain `.tar.gz` the workflow names
it and the release notes tell users to download
(`build-release.yml` line ~254: "Download `fiedle400-linux-x64.tar.gz`,
extract it, then `./install.sh`").

Not yet investigated. The most likely mechanism (not confirmed): GitHub's
`actions/upload-artifact@v4` always zips whatever it's given for storage;
`actions/download-artifact@v4` unzips it back to the original file
*within the same workflow run*, so the two steps inside
`build-release.yml` should round-trip cleanly to the original
`.tar.gz`. But if the extra `.zip` is coming from manually downloading
the workflow run's artifact via the Actions UI (which always wraps a
download in `.zip` regardless of the artifact's own name/content), that
would be a UI-download quirk, not a bug in the published GitHub Release
asset itself -- the two need to be told apart before concluding anything
is actually broken in the shipped release.

## Criteria

- [x] Determine exactly where the extra `.zip` layer is observed: the
      published GitHub Release asset itself, or a workflow-run artifact
      downloaded from the Actions UI
- [ ] If it's the published Release asset: fix the workflow so the
      asset uploaded to the Release is the plain `.tar.gz`
- [x] If it's only the Actions-UI artifact download: no code fix needed,
      just confirm and note it's expected GitHub behavior, not a release
      defect
- [x] Tests pass

## Execution Notes

Done 2026-11-02 (local): `gh release view --json assets` on the latest published release
(`v0.5.0`) lists the Linux asset as plain `fiedle400-linux-x64.tar.gz` -- no `.zip` layer.
Confirms the second hypothesis: the `.zip` psytrap saw was from downloading a workflow-run
artifact via the Actions UI, which always wraps any download in `.zip` regardless of the
artifact's own name or content. The published Release asset itself, which is what the README
and release notes actually tell users to download, is correct as-is. No workflow change
needed.
