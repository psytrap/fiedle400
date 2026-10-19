# T-003: Worked example -- one real download, start to finish

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `DESIGN.md`

---

## Description & Context

Evaluating RefDiff's docs, I'd first dismissed its `CODE_WALKTHROUGH.md`
(one representative case traced phase-by-phase through every module) as
not worth a dedicated file for a two-collaborator project. psytrap
pushed back: "The walks it helpful for recap" -- and given how much of
this session was spent re-deriving protocol context across resets (the
Manual-mode decode saga alone took three separate passes), a concrete,
chained, real-bytes trace would have cut that cost materially.

`DESIGN.md` §3 "Download flow" already exists but stays at the
procedure level (step names, field meanings) with no concrete bytes --
useful as a map, useless for a fast recap of *what actually happens on
the wire*. `PROTOCOL.md` has the real bytes already, scattered across
per-opcode sections (§3.1 handshake, §3.2 session query with a real
vendor-capture `0xEC` frame, §3.5 storage reads with a real boundary
probe). The gap is that no single place chains them into one
continuous story.

Not adopting RefDiff's full scope: no phase-by-phase per-module
breakdown (13 `src/` modules there vs. a handful of functions here),
no visual/DOM transformation diagrams (not applicable), no multi-file
subagent-dispatch framing. Just one real session, start to finish, in
plain prose with real bytes, sized to actually get read in one sitting.

---

## Criteria

- [x] `DESIGN.md` has a worked-example section following §3 "Download
      flow" that traces one real download end to end: handshake ->
      session query (real `0xEC` bytes) -> storage reads (real offset
      behaviour from the boundary probe) -> `0xED` decode -> export --
      citing `PROTOCOL.md` sections rather than duplicating their
      tables.
- [x] Uses bytes already verified in this repo (no invented numbers).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Added `DESIGN.md` §3a right after the existing abstract "Download flow"
section. Six steps (unlock, session query, SpO2 read, pulse read,
decode, export), each citing a real byte sequence already verified
elsewhere in this repo rather than inventing a new example session:
the vendor capture's real `0xEC` frame (PROTOCOL.md §3.2, 2026-09-06,
243 raw samples), the real boundary-probe finding that the storage-read
offset is a sliding window and not a page index (§3.5, the exact
mechanism behind T6), and the MSB-reassembly formula for `0xED`
subframes (§3.5). Explicitly noted the one thing this does *not* cover:
the Manual-mode protocol, which is a separate, not-yet-implemented
path with its own worked example already in PROTOCOL.md §3.14.

Did not adopt RefDiff's full `CODE_WALKTHROUGH.md` shape (per-module
phase breakdown, visual/DOM diagrams) -- this project's download path
is a handful of functions, not 13 modules, so one continuous six-step
narrative does the same job at a fifth of the length.

Tests: 273 run, OK (skipped=7) -- docs-only change, no code touched.
