Frozen. New work goes through `../tickets/` instead -- see
`tickets/README.md` and
[T-001](../tickets/done/2026-W43/T-001-adopt-ticket-strategy.md) for why.

- Active: lands flat here, directly in `handoff/`, same as before --
  only for a one-off local/cloud delegation that, for some reason, can't
  go through `tickets/`; move it into `archived/<CW>/` once answered.
- `archived/<CW>/`: closed request/response pairs, one subfolder per ISO
  calendar week (`2026-W42` etc.) they were written in. Contents stay
  as-is once filed; still cited by filename elsewhere in the docs
  (`docs/RELEASE_PLAN.md`, `CHANGELOG.md`) -- cite the full path,
  e.g. `handoff/archived/2026-W42/clean-audit-response.md`.
