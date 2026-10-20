# T-022: HTML viewer draws a false desaturation event across a multi-session gap

- **Status:** Open
- **Priority:** Normal
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/spo2_viewer.py:128` (`x(i)`, purely index-based pixel mapping)
  - `fiedle400/desat.py` (`detect_events`, operates on a flat index-ordered array)
  - `fiedle400/cli.py:1060` (`_open_spo2_viewer(all_records, saved_path)`, the
    live wizard viewer path)
  - `fiedle400/export.py` (`build_spo2_binary`, already fixed for this in the
    saved file by T-020 -- this ticket is the viewer catching up to that)

---

## Description & Context

Found by psytrap testing the fresh pipx install (v0.4.21) against the real
device: downloaded both real stored sessions, chose "Open it in the HTML
viewer now?", and saw a red band across what was visually the gap between
the two sessions, with a line drawn straight through it.

**Root cause, confirmed by reproduction.** `fiedle400/spo2_viewer.py`'s
chart positions every record by **array index**, not by its real
`timestamp`:

```
function x(i) { return padL + (count <= 1 ? 0 : ((i - vs) / (count - 1)) * plotW); }
```

`fiedle400/desat.py`'s `detect_events` works the same way -- it sees a flat
`spo2` array and treats every adjacent pair of entries as one second apart,
with no concept of each record's real elapsed time. Reproduced directly
against the two real device sessions used for T-011/T-020 (concatenated,
pre-T-020-fix values -- i.e. exactly what the live viewer path still uses
today): session 1 ends around 97%, session 2 starts around 94-97% about
three real minutes later. `detect_events` reports:

```
[{'start': 141, 'nadir': 167, 'from_pct': 98, 'to_pct': 94}]
```

a fabricated "desaturation event" spanning the session boundary -- the
detector read a 3-minute real gap as if it were a 26-second decline,
because the two sessions' records sit at adjacent array indices with no
gap between them in the data the viewer actually receives.

**Why this slipped past T-020.** T-020 fixed exactly this class of problem
-- but only in `fiedle400/export.py`'s `build_spo2_binary`, which pads the
*saved file* with sentinel records for the real elapsed gap. It did not
touch the record list used by the **live** viewer path:
`fiedle400/cli.py:1060` calls `_open_spo2_viewer(all_records, saved_path)`
with `all_records` -- the raw, un-padded, per-session-concatenated list --
not the gap-padded data that ends up in `saved_path` on disk. The saved
`.spo2` file and what the user sees in the browser immediately after are
now inconsistent: the file correctly shows the gap as probe-out, the live
viewer draws a fabricated event through it.

This also means a future `fiedle400 view FILE` (T-013), if it reads the
saved (now-correct) file back, would **not** have this problem -- it's
specific to the live, same-session, un-padded `all_records` path.

**Broader than one call site.** `fiedle400/desat.py`'s `detect_events` and
`summarize` make the identical assumption as the chart's `x(i)` -- every
adjacent pair of `spo2` array entries is one real second apart -- with
nothing in their signature or docstring saying otherwise. T-018's own
validation (T-019) only ever exercised one continuous recording, so this
was never caught there; see the note added to
`tickets/done/2026-W43/T-018-desaturation-events-and-basal-spo2.md`. A fix
scoped only to `cli.py`'s call site (e.g. pre-padding `all_records` before
handing it to the viewer) would paper over the viewer but leave
`desat.py`'s own assumption undocumented and still wrong for any other
caller that passes it genuinely gapped data.

---

## Criteria

- [ ] The live viewer path (`_open_spo2_viewer`/`all_records`) gets the
      same gap-awareness T-020 gave the file writer -- either by running
      `all_records` through the same gap-fill logic before building the
      viewer HTML, or a different fix, but the inconsistency between saved
      file and live viewer is resolved one way, not left standing.
  - Consider whether `x(i)`'s pure index-based positioning and
    `desat.detect_events`'s pure array-adjacency assumption are the right
    long-term design even for a single session with no gaps (e.g. a device
    clock jump mid-session) -- fixing only the multi-session case without
    checking the single-session assumption would leave a narrower version
    of the same bug.
- [ ] A test reproducing this exact scenario (two sessions with a real gap
      between them, feeding `all_records` to `build_viewer_html` or
      `desat.detect_events` directly) that fails without the fix.
- [ ] Verified no false event survives the fix, using the reproduction
      above (or equivalent) as a before/after check.
- [ ] Version bumped via `scripts/bump_version.py` (product-code change).
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
