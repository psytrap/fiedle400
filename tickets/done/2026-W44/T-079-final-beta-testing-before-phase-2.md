# T-079: Final beta testing before Phase 2 (the minor version bump)

- **Status:** Done
- **Priority:** High
- **Owner:** Local
- **Scope & Relevant Files:**
  - `RELEASE_PLAN.md` §1 (Phase 2 rule: minor bump only after pre-flight
    passed, the GitHub Release is verified live, **and the feature work
    has been reviewed by the user**)
  - `fiedle400/__init__.py`, `pyproject.toml` (version, once this closes)
  - `tickets/open/T-074-auto-mode-single-session-erase-does-not-work.md`,
    `T-076-viewer-event-band-toggle.md`, `T-077-linux-release-asset-double-zipped.md`,
    `T-078-transient-first-command-usb-hiccup.md` (deferred findings from
    the `v0.4.41` cycle -- in scope to look at here, not necessarily fix)

---

## Description & Context

`v0.4.38` and `v0.4.41` are both shipped, tagged, published, and verified
([T-047](T-047-release-v0-4.md), now closed). `v0.4.41` in particular
carries real behavior changes beyond routine bug fixes -- most notably
**T-075** (every session's reported duration/record count doubled; every
prior release had silently under-reported it by half) and **T-072**
(Manual-mode erase newly implemented and confirmed against real
hardware). Per `RELEASE_PLAN.md` §1, Phase 2 (`scripts/bump_version.py
minor`) is the step that records this as a real shipped milestone
(`0.4.x -> 0.5.0`) -- but it only happens after psytrap has actually used
the beta and is satisfied it's solid, not automatically once the gates
are green.

This ticket is that final, hands-on confidence pass: using `fiedle400`
day-to-day (not just running gates) against the real device for a while,
on whatever recordings come up naturally, before calling `v0.4.x` done
and bumping to `0.5.0`.

## Criteria

- [x] Some real, everyday use of the shipped `v0.4.41` binary (not a
      scripted gate run) -- download, view, clear, across a few sessions
      over a few days, on whatever recordings actually happen
- [x] No new finding from that use that should block Phase 2 (if one
      turns up, it gets its own ticket, same as this cycle's T-074/076/
      077/078; this ticket just has to wait for it or decide it's
      non-blocking)
- [x] psytrap explicitly confirms: ready for Phase 2
- [x] `scripts/bump_version.py minor` run, `0.4.x -> 0.5.0`
- [x] Tests pass

## Execution Notes

**2026-10-27/28 (real-device use, several long recordings):** Beyond the
scripted gates, the device saw substantial real day-to-day use over this
window -- including the T-083 Arduino+servo wiggler fixture runs, several
multi-hour Auto-mode sessions, and one real 11h38m52s/41,932-record
Manual-mode recording used repeatedly for download-reliability testing.
This use surfaced two real findings, both their own tickets (same pattern
as this cycle's T-074/076/077/078):

- [T-082](../done/2026-W44/T-082-wizard-erase-reports-success-but-sessions-persist.md)
  (wizard erase reporting success without persisting) -- investigated at
  length, root cause not conclusively nailed down, mitigated with a
  longer settle delay; left open as a possible-recurrence watch, not
  blocking.
- [T-094](../done/2026-W44/T-094-manual-mode-long-download-resume-budget-exhausted.md)
  (Manual-mode download of a long recording losing 97-100% of its
  samples) -- found, root-caused (an out-of-order-frame handling bug,
  not the retry budget itself as first suspected), fixed, and confirmed
  with a 10x full-length real-hardware re-download: byte-for-byte
  identical across all 10 runs, 0 missing samples. This was a real,
  serious bug that only a long real recording could have surfaced --
  exactly what this ticket's "whatever recordings actually happen"
  criterion was for.

psytrap (2026-10-28): "t79 is complete I'd say. Lots of long recordings
with some findings" -- explicit confirmation that T-094's fix (now
shipped and installed locally as `v0.4.43`) closes out the beta period
with no further blocking findings. `scripts/bump_version.py minor` run:
`0.4.43 -> 0.5.0`. Full suite passes (423 tests, 7 skipped -- live-only).
