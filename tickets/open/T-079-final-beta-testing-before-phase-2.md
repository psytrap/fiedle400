# T-079: Final beta testing before Phase 2 (the minor version bump)

- **Status:** Open
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

- [ ] Some real, everyday use of the shipped `v0.4.41` binary (not a
      scripted gate run) -- download, view, clear, across a few sessions
      over a few days, on whatever recordings actually happen
- [ ] No new finding from that use that should block Phase 2 (if one
      turns up, it gets its own ticket, same as this cycle's T-074/076/
      077/078; this ticket just has to wait for it or decide it's
      non-blocking)
- [ ] psytrap explicitly confirms: ready for Phase 2
- [ ] `scripts/bump_version.py minor` run, `0.4.x -> 0.5.0`
- [ ] Tests pass

## Execution Notes

(Not started.)
