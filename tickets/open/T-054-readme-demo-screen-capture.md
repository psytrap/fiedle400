# T-054: Add a demo screen capture to README.md

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `README.md`
  - a new image/gif asset (location TBD, e.g. `docs/` or repo root)

---

## Description & Context

`README.md` currently has no screenshot or screen capture of the tool in
action -- a new visitor sees only command examples and prose, no visual
of what `fiedle400 view`'s HTML viewer (the project's main deliverable
since T-005/T-012) actually looks like. A short demo (static screenshot,
or a GIF of the wizard running end-to-end into the viewer) would make
the README's value proposition legible at a glance.

Needs a decision on scope: a single static screenshot of the HTML viewer
showing a real (or `hwsim`) recording, vs. a short animated GIF of the
CLI wizard flow. Needs real or simulated data either way -- not a stored
device recording that should be committed as-is (check
`.agents/rules/implausible_data_warning.md` and the T-034-style clean-up
conventions for what belongs in the repo vs. `output/`/gitignored paths).

---

## Criteria

- [ ] Capture format decided (static image vs. GIF) and asset added at a
      sensible path, sized reasonably for a README (not a multi-MB file)
- [ ] `README.md` references it near the top (after the intro, before or
      alongside the command reference)
- [ ] Asset uses simulated (`hwsim`) or otherwise non-sensitive sample
      data, not a real stored recording
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
