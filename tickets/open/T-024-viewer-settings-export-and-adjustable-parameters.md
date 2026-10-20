# T-024: Viewer export/save settings button

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (statistics panel)
  - `tickets/open/T-023-viewer-blocked-areas-and-exportable-settings.md`
    (exclusion-selection interaction this ticket would persist)
  - `tickets/done/2026-W43/T-025-viewer-configurable-saturation-parameters.md`
    (parameter UI this ticket would persist -- **done**, 2026-10-20)

---

## Description & Context

psytrap: add an export/save button so the user can keep their configured
viewer settings rather than losing them every time the page is a fresh
one-shot temp file (T-005's own design: generate, open, clean up).

**Split 2026-10-20, twice.** Originally one ticket covering area-exclusion
selection, adjustable analysis parameters, and export/save together. Split
into **T-023** (area-exclusion selection) and this ticket (export/save +
adjustable parameters); then split again into **T-025** (the parameter UI
itself) and this ticket, now just the persistence mechanism.

**T-025 is done** (2026-10-20): drop %, min duration and criteria level are
now adjustable inputs in the viewer, recomputed client-side
(`recomputeEvents()` in `fiedle400/spo2_viewer.py`), verified against the
real SpO2 Assistant numbers from T-019. This ticket now has a concrete
first thing to persist. **T-023 (area exclusion) is still open/deferred.**

**Not decided here, for whoever picks this up:**
- What "export/save" actually means for a one-shot temp-file page (T-005):
  download a small JSON settings file the user keeps and could reload into
  a later viewer session? Browser `localStorage` tied to the recording's
  identity? Something else -- this needs a concrete mechanism, not just
  the request.
- Whether reloading a saved settings file into a *different* recording
  (not the one it was made for) should be allowed, warned about, or
  rejected.
- Whether to ship against T-025's parameters alone now, or wait for T-023
  too so the export format only needs defining once.

---

## Criteria

- [ ] Scope above decided with psytrap (ship against T-025 alone now, or
      wait for T-023 too) and this ticket updated before implementation
      starts.
- [ ] An export/save action that persists T-025's configured parameters
      (and T-023's excluded ranges, once that lands, if waited for) in a
      concrete, chosen format.
- [ ] A test covering the export format (and round-trip, if a
      reload/import path is built) that fails without the change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
