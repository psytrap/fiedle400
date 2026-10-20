# T-018: Show desaturation events, ODI and Basal SpO2 in the HTML viewer

- **Status:** Open (placeholder)
- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py` (statistics panel and chart)
  - `SPO2_FORMAT.md` §7 (the vendor definitions this implements)
  - `tickets/done/2026-W43/T-017-desaturation-and-basal-spo2-definitions.md`
    (research this follows up on)

---

## Description & Context

Placeholder opened at psytrap's request together with T-017, to hold the
implementation of the definitions T-017 researched. T-007 items 5
(desaturation events and index) and 6 ("Basal SpO2") were deferred because
no definition existed; `SPO2_FORMAT.md` §7 now has one, decoded from
`SpO2.exe` and the vendor manual.

Not ready to execute yet. Before it is, decide:
- whether to follow the vendor algorithm exactly (§7.2: baseline = local
  peak, depth >= 4 %, 10-180 s descent, merge on <= 1 % rebound) so the
  numbers match SpO2 Assistant, or a standard ODI definition, or both
  labelled clearly;
- which values to show (Total Event, Index, Adjusted Index, Avg. Low SpO2,
  Basal SpO2, Artifact %) and whether the events are marked on the chart;
- what to check it against: T-019 validates the decoded algorithm in the
  real SpO2 Assistant with a synthetic probe recording; start this ticket
  only after T-019.

---

## Criteria

- [ ] Scope above decided with psytrap and this ticket updated.
- [ ] Values match SpO2 Assistant on the T-019 probe recording, or the
      difference is explained.
- [ ] A test that fails without the change.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
