# Project Contract (read this first)

`fiedle400` is a small open-source CLI (a few hundred potential users) for the Pulsox
PO-400 / Contec CMS-50 pulse oximeter. Keep changes small, boring and tested; do not
over-engineer.

## Source of truth, in order

1. Real-device recordings (`tests/fixtures/*.trace.json`, `analysis/*.pcap`).
2. `PROTOCOL.md` (byte-level protocol). Its Manual-mode sections (§3.14 and the German
   mirror, `analysis/po400_bytemap_reference.md`) are unverified: flag problems there,
   do not silently rewrite them.
3. `DESIGN.md` (architecture), `RELEASE_PLAN.md` (gates, open findings, version rules),
   `CHANGELOG.md` (how each finding was found and fixed).
4. The code. If code and docs disagree, say so and fix one; never leave both.

## Commands

```bash
python3 -m unittest discover -s tests        # whole suite: simulator + unit, no hardware
python3 -m pyflakes fiedle400 tests          # no new warnings (pip install pyflakes; the `readline` side-effect import in cli.py is the one known exception)
python3 scripts/bump_version.py show         # versions in all manifests
fiedle400 selftest                           # read-only check on a real device (local only)
FIEDLE400_LIVE=1 python3 -m unittest tests.test_device_live   # real-device tests (local only)
```

## Invariants (do not break)

- **Never erase device flash** and never run `clear` or other destructive opcodes in tests
  or tooling. Stored sessions are the user's real data. The simulator refuses them.
- `download`, `sessions`, `info`, `selftest` are read-only on the device.
- A read's "page" argument is a **sample offset**; the `0xEC` header count is **raw 2 Hz
  samples**; a record is the average of two raw samples. In stored data, finger-out
  is detected from out-of-range decoded values (the vendor's 127 / 255 sentinels), never from a
  flag byte; no real recording has shown one yet (T1 is open). (Details: PROTOCOL.md §3.5, DESIGN.md §3.)
- Failures end in one clear line and a nonzero exit code, not a traceback
  (`cli.run_guarded`). Missing optional pieces (matplotlib, `hid`) print an install hint.
- The tool is `fiedle400`; the device stays "PO-400" in user text. `PO400_*` variables
  and `po400` settings migration are intentional compatibility shims.
- The Linux backend (`hidraw`) uses the standard library only. Do not add dependencies
  without asking.
- Never state a protocol fact you have not seen in a recording; mark hypotheses as such.
- Never show a default or placeholder for a value the device did not send. Print "not
  reported by the device" instead. The real PO-400 sends no firmware version or serial
  number, and its clock reply (`0xF2`) is the same bytes every time.

## Tests

- Every behaviour change comes with a test that fails without it. Prefer the simulator
  (`tests/hwsim.py`) and real-trace fixtures over hand-built bytes and mocks.
- Tests must give the same result on every machine: no real `/dev`, `/sys`, user config,
  attached device, or `FIEDLE400_*`/`PO400_*` variables (use `hwsim.scrub_env`). A test
  that passes only because of what the developer's machine has is a bug.
- Sleeps in the engine are real for real devices: tests patch `fiedle400.engine.device.time`
  with `VirtualClock`.
- New fixtures: record with `tests/capture_tools/record_exchange.py` (read-only), review
  for personal data before committing.

## Delivery

- Work in the cloud copy; deliver `git`-applicable patches `changes/NNNN-short-name.patch`
  (next free number). Local applies, tests, commits.
- One patch per request. Findings and the fixes they call for go in that one patch, not in a
  list of proposed patches. A follow-up to a patch that has not been applied yet is merged
  into it instead of getting a new number.
- Version bumps only via `scripts/bump_version.py`, following RELEASE_PLAN §1. A patch that
  changes product code bumps the patch version.
- `analysis/*.md` use CRLF line endings, and the German bytemap contains a NUL byte. Edit
  them without converting line endings (in Python: `open(p, newline="")`).
- Definition of done: suite green, pyflakes clean, docs touched by the change updated
  (README for user-visible behaviour, PROTOCOL.md for protocol facts, RELEASE_PLAN for
  findings/gates), no leftover debug prints. For a periodic deeper pass (before a
  release, or after a batch of patches), see `.agents/rules/code-review-standards.md`.

## Glossary

- **raw sample**: one 2 Hz device value. **record**: one exported second (two raw averaged).
- **offset / page**: start position, in raw samples, of a `9D 04` read.
- **T1..T8**: findings; current status in RELEASE_PLAN §3d, full history in CHANGELOG.md. **G1..G8**: release gates (RELEASE_PLAN §2).
- **handoff/**: frozen archive of pre-ticket cloud briefs; still cited by filename
  elsewhere in these docs, but superseded by `tickets/` for new work.
- **tickets/**: numbered work items (`T-NNN-slug.md`) replacing `handoff/`; see
  `tickets/README.md`.

# Workspace Rules

## Rule: Workspace Output Directory Hygiene

- Store temporary test artifacts, scratch plots, and agent workfiles under `output/`.
- Do NOT hardcode or default `output/` in the end-user product (`fiedle400`); the product defaults to saving in the current working directory (`.`).

## Rule: Division of Labour — Cloud vs Local

Work on this project is split between two environments. The split is not a
preference; it follows from where the hardware is.

- **Cloud** has read-only access to this folder. It can read all code, but the
  Pulsox PO-400 is physically attached to the local machine only, so the cloud
  can neither run the hardware tests nor observe device behaviour.
- **Local** has the device attached and is the only place hardware work can
  happen.

Therefore:

| Area | Owner | Action |
|---|---|---|
| Product/test code fixes | Cloud | Develops the fix, delivers a numbered patch |
| Hardware layer | Local | Diagnoses **and** fixes directly |
| Applying patches | Local | Inspect, dry-run, apply, verify, commit, report |

"Hardware layer" means device access and permissions (udev rules), running the
hardware suite, driver/backend behaviour, and test-harness problems caused by
real-device quirks — e.g. the libusb backend detaching the kernel usbhid driver,
fixed locally in commit 69bb1bb.

Local does not author product-code fixes: they would diverge from the cloud copy
and conflict on the next patch. Local still diagnoses, reports the mechanism and
recommends a fix — it just does not implement it.

## Rule: Delegation Path

Delegate investigations to the cloud by opening a ticket in `tickets/open/`
(`Owner: Cloud`, see `tickets/README.md`), then telling the cloud it is
there. Do not spawn local subagents for this. This replaced the old
`handoff/` convention (see `tickets/done/T-001-adopt-ticket-strategy.md`);
`handoff/` itself is frozen, not deleted, and still cited by filename
elsewhere in these docs.

`tickets/` is tracked in git on purpose. Do NOT use `output/` for anything the
cloud must read — it is gitignored and therefore invisible to a git-based sync.

A ticket's `Description & Context` must carry what the cloud cannot observe for itself:

- the symptom, with the exact command and the observed numbers;
- hardware facts and any measurements taken locally;
- current repo state, including applied-but-uncommitted patches;
- an explicit statement of what is NOT yet known, so the cloud does not
  mistake a hypothesis for a finding;
- what the local side can run on request, and any safety constraints
  (never erase device flash — stored sessions are real data).
