# T-027: Automated test coverage for the viewer's ported JS detection logic

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`detectEvents`/`summarizeEvents`, the JS
    port of `fiedle400/desat.py`'s `detect_events`/`summarize`)
  - `fiedle400/desat.py` (the Python original these must keep matching)
  - `tests/test_spo2_viewer.py` (existing markup-only tests; no logic
    coverage for the JS itself)

---

## Description & Context

T-025 added `detectEvents`/`summarizeEvents` to `fiedle400/spo2_viewer.py`
-- a line-by-line JS port of `desat.py`'s `detect_events`/`summarize` --
so the viewer's desaturation parameters (drop %, min duration, criteria
level) can be changed live in the browser without a server round-trip.
That logic's only verification right now is a **one-time manual pass**:
loading the T-019 probe recording in a real browser via this session's own
Browser-pane tooling and checking the recomputed numbers by hand (documented
in `T-025`'s Execution Notes). Nothing re-runs that check automatically,
and CI has no browser at all (same limitation already noted for T-018's
JS).

**The risk this leaves.** A future edit to either `desat.py` or its JS
twin -- fixing a bug, adjusting a threshold, changing the merge logic --
can silently desync the two implementations. The Python side has
`tests/test_desat.py`; the JS side has nothing. Nobody would notice a
port drift until someone happened to compare numbers by eye again.

**Not decided here, for whoever picks this up:** what "automated" means
concretely for JS embedded in a Python-generated HTML template, with CI
having no browser:
- A Node-based test runner (dev-only dependency, not shipped) that
  extracts/evaluates the ported functions and runs the same cases
  `tests/test_desat.py` already covers, asserting parity with
  `desat.py`'s own results.
- A headless-browser CI step (Playwright/Puppeteer or similar) that
  actually loads a built viewer page and drives the inputs, closer to
  T-025's manual verification but automated and repeatable.
- Extracting the shared detection logic to data (e.g. generate expected
  JS output from Python at build time, comparing structurally) rather than
  maintaining two hand-written implementations at all -- a larger
  refactor, but would remove the port-drift risk at the root instead of
  just testing for it.

Whichever approach is chosen should run in CI (`.github/workflows/tests.yml`)
if it reasonably can, not just locally -- a check nobody runs catches
nothing. If a new dev-only tool/runtime (Node, a browser automation
package) is needed, flag that explicitly rather than adding it silently
(AGENTS.md: "Do not add dependencies without asking").

---

## Criteria

- [ ] A concrete testing approach chosen and justified in this ticket's
      Execution Notes (not left as the three options above).
- [ ] The JS `detectEvents`/`summarizeEvents` logic has automated test
      cases covering at least what `tests/test_desat.py` already covers
      for the Python original (candidate building, oscillation merging,
      acceptance thresholds, the T-019 real-number cases).
- [ ] Parity between the Python and JS implementations is asserted
      somewhere, not just each tested independently -- a test that would
      catch the two drifting apart.
- [ ] Runs in CI if the chosen approach makes that feasible; if not,
      explicitly say why and how it's run instead (manual checklist step,
      a separate local-only command, etc.).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
