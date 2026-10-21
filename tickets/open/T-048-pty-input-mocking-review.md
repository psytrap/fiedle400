# T-048: Review whether the Windows CI job needs more than `builtins.input` mocking

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `tests/test_cli_interactive.py` (drives the wizard via `builtins.input`)
  - `.github/workflows/tests.yml` (the `windows-latest` leg)

---

## Description & Context

Split out of [T-047](T-047-release-v0-4.md), from `RELEASE_PLAN.md` §3g's
own TODO (psytrap, 2026-10-16): `tests/test_cli_interactive.py` drives the
interactive wizard by patching `builtins.input` with a canned
`side_effect` list -- confirmed pure Python mocking, no real stdin/console
involved, so it behaves identically on all three `tests.yml` runners and
isn't actually testing anything Windows-console-specific about the
wizard's interactive behaviour.

Worth a look at whether a more realistic approach (a real pty / real
subprocess with piped stdin) would catch bugs the mock can't -- e.g.
console encoding quirks, Windows-specific `readline` behaviour. **No known
bug motivates this** -- it is a gap in how faithfully the test doubles for
a real terminal, not a response to anything broken.

What is NOT known:
- Whether a pty-based test is even practical on `windows-latest` (ptys are
  a Unix concept; Windows has ConPTY, a different API) without adding a
  dependency.
- Whether any of the console-encoding work already done (B7,
  `RELEASE_PLAN.md` §3) would actually have been caught earlier by a more
  realistic test, or whether that bug class is already covered some other
  way.

---

## Criteria

- [ ] A decision: worth a pty/subprocess-based interactive test, or the
      current `builtins.input` mock is good enough for what this project
      needs -- with a reason either way.
- [ ] If worth doing, filed as its own follow-up ticket with an
      implementation sketch, not carried out inline here.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
