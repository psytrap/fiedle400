# Rule: Code-Review Standards

## Trigger
- Before a release tag, after a batch of patches, or whenever explicitly
  asked for a "clean code" / "clean docs" / "clean test" pass. Not on
  every commit -- this is a periodic audit, not a per-change gate.
- Usable by either side (local or cloud): it is a rubric, not
  hardware-gated work.

## Clean code
- Dead code: unused functions, imports, or branches that can never run
  (check with a real grep/call-site search, not a guess).
- Duplicated logic that should be a shared helper (two near-identical
  loops, the same parsing done twice).
- Debug prints or `TODO` markers left in from development.
- Magic numbers without a named constant or a comment explaining the
  byte offset/opcode they encode -- this project's code is full of
  protocol byte math, so an unexplained `[5]` or `0x7F` is a smell here
  specifically, not just generically.
- Inconsistent naming for the same concept across files (e.g. `offset`
  vs `page` vs `window` for the same value -- this exact confusion was a
  real, fixed bug: CHANGELOG.md T6).

## Test smell
- Duplicated setup that should be a fixture or shared helper.
- Assertions too weak to catch the regression the test is named for
  (asserts `rc == 0` but never checks the actual output that mattered).
- Tests that pass for the wrong reason (mocks so loose they'd still pass
  after the real implementation broke).
- Dead or unreachable test code (see T-001's note on the stranded
  `if __name__ == "__main__"` guard, commit `065785d`, for a real
  example of this exact shape).
- Environment-dependent tests that only pass because of what this
  specific machine has attached, installed, or returns right now
  (`RELEASE_PLAN.md` §3e has the full writeup and the incident that
  prompted it).

## Coverage proportionality
Ask both directions, not just "is there a test":
- **Too little?** Does a real failure mode (a wrong byte offset, a
  wrong checksum, a device that never answers) have a test that would
  actually catch it, or only a happy-path test?
- **Too much?** Is there a test asserting something that can't
  meaningfully break, or three tests covering the exact same case with
  different mock data for no reason?

## What this replaces
Formalizes the ad-hoc pass already done once (patch 0014, prompted by a
one-off `RELEASE_PLAN.md` TODO) into a standing rubric, so the next pass
doesn't reinvent the criteria. Adapted from evaluating
`github.com/psytrap/refdiff`'s `REVIEW_GUIDE.md` §2.5-2.6 -- the
severity-tiered findings register and diff-audit checklist there already
have po400 equivalents (T1-T8, `RELEASE_PLAN.md` §1) and aren't
duplicated here.
