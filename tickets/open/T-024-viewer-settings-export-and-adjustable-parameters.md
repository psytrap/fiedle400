# T-024: Viewer export/save settings button and adjustable analysis parameters

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (statistics panel, `desat.py` params wiring)
  - `fiedle400/desat.py` (`DROP`/`MIN_TIME`/`CRITERIA` -- currently fixed
    constants, not exposed in the page)
  - `tickets/done/2026-W43/T-018-desaturation-events-and-basal-spo2.md`
    ("Not done: changing the parameters in the page")
  - `tickets/open/T-023-viewer-blocked-areas-and-exportable-settings.md`
    (split from this ticket -- the exclusion-selection interaction this
    one would persist, if T-023 lands first)

---

## Description & Context

psytrap: add an export/save button so the user can keep their configured
viewer settings -- analysis limits/thresholds (desaturation drop %, minimum
duration, criteria level) and, once T-023 exists, any excluded ranges --
rather than losing them every time the page is a fresh one-shot temp file
(T-005's own design: generate, open, clean up).

**Split 2026-10-20** from a combined ticket that also asked for click/drag
area-exclusion selection in the chart -- that's now **T-023**. This ticket
is the persistence/configuration half: making the analysis parameters
adjustable in the page at all, and an export/save mechanism for them (and,
once it exists, T-023's exclusion state).

**Pulls in T-018's own leftover item.** T-018 shipped `desat.py` with fixed
constants (`DROP=4`, `MIN_TIME=10`, `CRITERIA=88`) and explicitly left
"changing the parameters in the page" as not done. That's this ticket's
starting point regardless of what T-023 does.

**Not decided here, for whoever picks this up:**
- What "export/save" actually means for a one-shot temp-file page (T-005):
  download a small JSON settings file the user keeps and could reload into
  a later viewer session? Browser `localStorage` tied to the recording's
  identity? Something else -- this needs a concrete mechanism, not just
  the request.
- Whether reloading a saved settings file into a *different* recording
  (not the one it was made for) should be allowed, warned about, or
  rejected.
- Whether this ticket should wait for T-023 to land first (so it can
  persist exclusion state from day one) or ship parameter-adjustment and
  export on its own, with exclusion-state persistence added once T-023
  exists -- either is fine, but pick one rather than blocking indefinitely
  on the other ticket's own open scope decision.

---

## Criteria

- [ ] Scope above decided with psytrap and this ticket updated before
      implementation starts (same pattern as T-018's own placeholder
      phase).
- [ ] Desaturation parameters (drop %, min duration, criteria level)
      adjustable in the page, not just the fixed `desat.py` constants.
- [ ] An export/save action that persists the configured parameters (and
      T-023's excluded ranges, if that ticket has landed) in a concrete,
      chosen format.
- [ ] A test per piece (parameter adjustment, export format, and
      round-trip if a reload/import path is built) that fails without the
      change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
