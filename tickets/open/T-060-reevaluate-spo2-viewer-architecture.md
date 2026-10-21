# T-060: Re-evaluate `spo2_viewer.py`'s architecture

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (581 lines)
  - `tests/test_desat_js_parity.py`, `tests/test_spo2_viewer.py`

---

## Description & Context

psytrap request: re-evaluate `spo2_viewer.py`. No specific symptom named --
this is a step-back design review, not a bug report, prompted by the file's
growth and the amount of pending/recent work that touches it.

**What's already known about this file, surfaced across recent tickets:**
- It's a single 581-line Python module whose core job is building one
  self-contained HTML page: Python-side export logic plus a large inline
  JavaScript string (the viewer's client-side code, including a near-verbatim
  **port of the SpO2/pulse desaturation detector** from `fiedle400/desat.py`
  into JS -- T-027/T-029/T-030).
- That JS port is kept honest only by `tests/test_desat_js_parity.py`,
  which extracts the JS between `// BEGIN desat-port` / `// END desat-port`
  markers and runs it under real Node, comparing against the Python
  implementation. This works, but it's a parity test between two
  hand-maintained copies of the same algorithm, not a single source of
  truth -- a bug present in *both* copies (the `st=0` sentinel-index
  quirk flagged in T-045) can never be caught this way, by construction.
- `tests/test_spo2_viewer.py` only pins source-level string facts (text
  present/absent in the generated HTML), it doesn't execute `stats()`/
  `render()` -- so DOM-driving logic is effectively untested except
  through the parity harness's narrower scope (T-032's review found two
  real display-layer bugs this way, T-044).
- Several open tickets want to add more to this same file: a comment
  field (T-056), an editable username (T-058), both already flagged as
  needing a joint persistence design since the page is static with no
  backing store. Area-exclusion selection and settings export (T-023,
  T-024, deferred) would add more still.

**What this ticket should actually produce:** a decision, not a rewrite --
whether the current shape (one big Python module, inline JS string,
cross-language parity tests) still fits now that T-056/T-058 want
interactive, stateful features added on top of what was originally a
read-only report page, or whether something should change first (e.g.
splitting the JS to its own asset, a different testing strategy, or
explicitly deciding "no, this is fine, keep going as before").

---

## Criteria

- [ ] Current architecture and its known sharp edges written up (this
      ticket's Description already starts that list; complete it)
- [ ] Explicit decision recorded: keep the current shape, or change it
      (and if changing, what the new shape is) -- before T-056/T-058 start
      implementation, since they'd build on top of whatever is decided
      here
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
