# T-069: Automated test coverage for the viewer's interactive JS behavior

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (the inline `<script>` -- chart drawing,
    zoom/pan, tooltip hover, checkbox toggles, print)
  - `tests/test_spo2_viewer.py` (today's coverage)
  - `tests/test_desat_js_parity.py` (today's *other* JS coverage)

---

## Description & Context

Asked while reviewing what JS testing exists in the project (2026-10-21).
Today there are two kinds of JS-related automated checks, both real but
narrower than "the JS works":

- `tests/test_desat_js_parity.py` (T-027): extracts the actual
  `detectEvents`/`summarizeEvents`/`summarizePulse` block from the shipped
  HTML and runs it under Node, comparing output against `desat.py` for a
  battery of cases. This covers the *data-computation* JS only.
- `tests/test_spo2_viewer.py`: checks the *generated HTML/JS as text* --
  that a button exists, that a checkbox is wired to the right id, that no
  network-loading code is present, etc. It never executes the interactive
  code paths.

**Not covered by anything:** canvas chart drawing, zoom/pan mouse
handling, tooltip hover, the checkbox toggles' actual effect on what's
drawn, and the print stylesheet's actual effect -- all exercised only by
hand in a real browser, never by the automated suite.

## Criteria

- [ ] Decide an approach (e.g. a headless/simulated DOM run under Node,
      or browser automation) and record the trade-off against the
      zero-dependency promise (G4) -- this is a dev-time test tool, not a
      shipped dependency, but still needs a decision on what's acceptable
      to require locally/in CI
- [ ] At least the chart's zoom/pan and the channel-toggle checkboxes'
      actual effect on the drawn chart are covered
- [ ] Tests pass

## Execution Notes

(Not started.)
