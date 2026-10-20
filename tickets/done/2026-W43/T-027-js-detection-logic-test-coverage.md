# T-027: Automated test coverage for the viewer's ported JS detection logic

- **Status:** Done
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

- [x] A concrete testing approach chosen and justified in this ticket's
      Execution Notes (not left as the three options above).
- [x] The JS `detectEvents`/`summarizeEvents` logic has automated test
      cases covering at least what `tests/test_desat.py` already covers
      for the Python original (candidate building, oscillation merging,
      acceptance thresholds, the T-019 real-number cases).
- [x] Parity between the Python and JS implementations is asserted
      somewhere, not just each tested independently -- a test that would
      catch the two drifting apart.
- [x] Runs in CI if the chosen approach makes that feasible; if not,
      explicitly say why and how it's run instead (manual checklist step,
      a separate local-only command, etc.).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-10-20 (Claude, cloud copy).

Approach chosen: a Node-based parity test inside the normal unittest run, no npm packages, no
browser. `fiedle400/spo2_viewer.py` now marks the port with `// BEGIN desat-port` / `// END desat-port`
(constants, `detectEvents`, `summarizeEvents`). `tests/test_desat_js_parity.py` builds the page,
extracts that block, runs it with `node` in a subprocess (cases as JSON on stdin, results as JSON on
stdout) and compares events and every summary value with `desat.detect_events`/`summarize`. It is
skipped when `node` is not installed (`shutil.which`). Chosen over a headless browser because it
needs nothing installed beyond Node and runs in ms; chosen over generating the JS from Python
because that is a refactor the ticket did not ask for. Because the test runs the shipped page's
text, a drift in the template is what it catches.

CI: no workflow change needed. GitHub's ubuntu, windows and macos runners ship Node, so
`tests.yml` runs it already (it is a skip, not a failure, on a machine without Node).

Cases: every sequence of `tests/test_desat.py`; the T-019 probe from `scripts/make_desat_probe.py`
(`build_series()`; 7 / 8 / 9 events for the default, drop 3 and min_time 8 asserted for the JS
too); parameter variants (drop 3/4/5, min_time 4/8/10/12, criteria 85/88/90); 300 seeded random
sequences (seed 400: plateaus, staircase drops with rebounds, recoveries, None/127/0/255 gaps,
checked to produce more than 50 events); a case where every valid sample is inside an event (basal
SpO2 is not computed, T-031); an exact-tie rounding case.

Real drift found and fixed: the JS rounded with `Math.round(v * 100) / 100`, which is half-up and
works on an inexact product, while Python's `round(x, n)` goes to the even digit on exact ties
(for example a mean event duration of 10.25 s is 10.2 in Python and showed 10.3 in the viewer).
The fuzz and the tie case both failed on the old JS (verified by putting it back). `summarizeEvents`
now uses `pyRound`: `toFixed` (exact) plus an explicit exact-tie check. `desat.py` was not changed
for this. The T-031 basal change (no fallback to all valid samples) was already mirrored in the JS
and is covered by the parity test.

Tests: 5 in the new file; suite 358 run, 0 failures, 7 skipped (live device).
