# Handoff: clean-code / clean-docs / clean-test / clean-release audit

Written by the local side for the cloud, 2026-10-15.

**Repo state:** HEAD `9654913`, version `0.3.2`, 255 tests passing (7
skipped — opt-in live-device tests). `v0.2.17` is tagged and released
(GitHub Release, pre-release/alpha). `master` has `0.3.0`/`0.3.1`/`0.3.2`
open since that release — no new tag yet.

## The task

psytrap asked for a TODO to be tracked, now written up in
`RELEASE_PLAN.md` §3e under "**TODO (psytrap, 2026-10-15): broader
clean-code / clean-docs / clean-test / clean-release audit.**" Read that
entry for the exact scope; it is not duplicated in full here. Four areas:

1. **Clean code:** dead code, unused imports/functions, duplicated logic
   that should be a shared helper, leftover debug prints, inconsistent
   naming.
2. **Clean docs:** stale claims in `PROTOCOL.md`, `analysis/*.md`,
   `README.md`, `PACKAGING.md` that no longer match the current code —
   the *opposite* direction from the protocol-vs-hardware corrections this
   session made (code/doc drift, not protocol/hardware drift).
3. **Clean tests:** this folds in an earlier, narrower TODO already in the
   same `RELEASE_PLAN.md` section — a pass over `tests/` for duplicated
   setup that should be a fixture, assertions too weak to catch the
   regression they're named for, tests passing for the wrong reason,
   dead/unreachable test code, overfit mocks. There's also a related,
   separate TODO right above both of these in §3e (`psytrap`, same date):
   re-audit for environment-dependent tests that only pass because of what
   *this* development machine happens to have attached/installed (the
   `command_selftest` CI incident, `98a9b08` → `64e1c65` → `770daf0`, is
   the example that prompted it). Worth doing together since you'll be
   reading the same files for both.
4. **Clean release:** workflow files (`.github/workflows/*.yml`),
   `RELEASE_PLAN.md` itself for stale "today" status lines that no longer
   reflect reality, and repo-settings drift. One concrete example of the
   last category from this session: the repo's
   `default_workflow_permissions` was silently `read`, which caused the
   `v0.2.1` release job to build everything successfully and then fail
   only at the final "Publish GitHub Release" step with `Resource not
   accessible by integration` — the job's own `permissions: contents:
   write` block (already correctly written, with a comment explaining
   why) couldn't override the repo-wide ceiling. Fixed by flipping the
   repo setting directly (not something you can do from the cloud side —
   needs an org/repo admin action); look for other settings vs. docs
   mismatches of that shape.

## Suggested approach

This is read-heavy and cross-file by nature (you'll want to grep across
`fiedle400/`, `tests/`, `*.md`, `.github/`) — exactly the kind of thing
better suited to the cloud side than local, since it doesn't touch
hardware at all. Deliver findings the usual way: a patch (or a short list
of proposed patches if the four areas turn out to need separate review
cycles) in this `handoff/` directory, not applied directly — psytrap
reviews and applies per the project's existing division of labor.

One thing to flag rather than silently fix if you find it: anywhere the
audit would touch `PROTOCOL.md` or `analysis/po400_bytemap_reference.md`'s
Manual-mode sections (§3.14 / the German mirror) — those were extensively
corrected this session against live hardware and a cross-checked relayed
disassembly; treat any doc/code mismatch there as probably the *code*
being stale (Manual mode isn't implemented in `fiedle400` yet at all) or a
genuinely-still-open question (see §3.14.F's open-points note), not as a
doc bug to casually resolve.
