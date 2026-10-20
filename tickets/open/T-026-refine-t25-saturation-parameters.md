# T-026: Refine T-025's configurable saturation parameters

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Local or Cloud (live-device work needs Local; code changes
  follow the usual product-code convention either way)
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (`detectEvents`/`summarizeEvents`, the
    `#dropPct`/`#minDur`/`#critLevel` inputs)
  - `tickets/done/2026-W43/T-025-viewer-configurable-saturation-parameters.md`
    (what shipped and its own "Not done" list -- source of every item below)
  - SpO2 Assistant's live Analyseparameter dialog (Windows 8.1 laptop,
    `192.168.2.165`, reached per T-019/T-011's established method)

---

## Description & Context

T-025 shipped the SpO2-side desaturation parameters (drop %, min duration,
criteria level) as adjustable, live-recomputing inputs in the HTML viewer,
verified against three real SpO2 Assistant runs (T-019's probe recording:
7/8/9 events for default/drop=3/min_time=8). This ticket holds the loose
ends T-025's own closing notes left open, rather than letting them quietly
disappear once the ticket was marked Done:

1. **`criteria`'s valid range is assumed, not verified.** T-025's `#critLevel`
   input allows 1-99 %, but the live SpO2 Assistant dialog never showed
   this field's actual range (it wasn't visible in the T-019 screenshot --
   only `drop` 1-20 and SpO2 `min_time` 1-180 were). Check the real dialog
   directly (same machine/method as T-011/T-019) and correct the input's
   `min`/`max` if the vendor's own range differs.
2. **Pulse-rate parameters are still not implemented.** T-025 explicitly
   left them out because no pulse-event detector is decoded anywhere in
   this project. If that detector ever gets decoded (a separate,
   significant reverse-engineering effort -- not assumed to be quick),
   this ticket is where the pulse-side `#pulseDropPct`/`#pulseMinDur`
   inputs and their JS detector would go, mirroring T-025's SpO2-side
   pattern.
3. **No JS unit test exists for `detectEvents`/`summarizeEvents`.** T-025's
   verification was a one-time manual pass in a real browser (documented in
   its Execution Notes), not a repeatable automated check. CI has no
   browser, but consider: a lightweight Node-based test (no new Python
   dependency, just a dev-only JS runner) executing the same ported logic
   headlessly, so a future edit to `spo2_viewer.py`'s JS can't silently
   break the live-recompute path without a test catching it.
4. **Interaction with T-023 (area exclusion), if/when it lands.** T-025's
   own notes flagged that excluded ranges and parameter changes both affect
   the same event detection and need to recompute together. Not urgent
   while T-023 is still deferred, but worth revisiting together rather than
   bolted on independently later.

Not asking for all four at once -- items 1 and 3 are small, self-contained
verifications; item 2 is its own large undertaking (decoding an
undiscovered protocol detail) that shouldn't block on this ticket's other
items; item 4 is genuinely blocked on T-023 existing first.

---

## Criteria

- [ ] Item 1: `criteria`'s real valid range confirmed against the live
      SpO2 Assistant dialog (method: real machine, not guessed), and
      `#critLevel`'s `min`/`max` corrected if it differs from 1-99.
- [ ] Item 3: a repeatable automated check for `detectEvents`/
      `summarizeEvents` exists (Node-based or otherwise), not just a
      one-time manual browser pass.
- [ ] Items 2 and 4 either addressed or explicitly left for a further
      ticket, with the reason stated -- not silently dropped.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
