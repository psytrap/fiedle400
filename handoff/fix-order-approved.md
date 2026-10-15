# Handoff: fix order approved, T1 unblocked

For the cloud, re: `handoff/trace-response.md`'s proposed fix order. HEAD at
time of writing carries this file plus the RELEASE_PLAN updates below.

## Fix order: approved as proposed

T3 -> T6 -> T1 -> T2 -> T4/T7 -> T5. Proceed in that order.

## T1: unblocked (psytrap, 2026-10-15)

No longer a hard gate before touching the decoder. Proceed, but flag the fix
for double-checking rather than treating it as final:

- Byte 7 of a `0xED` frame is `m2` (PROTOCOL.md §3.5), not a status field.
  Stop deriving probe-out/searching/low-perfusion from it.
- The storage stream's own documented finger-out signal is a sentinel in the
  *decoded value itself*, not a flag byte: `analysis/bum400_20260906_100516.md`
  §4 -- SpO2 out of range -> `0x7F` (127, `---%`), pulse out of range -> `0xFF`
  (255, `--- bpm`). Use that instead.
- RELEASE_PLAN.md's T1 row carries the full note and now matches this.

Re-verify once the 5-10 minute recording (new TODO in RELEASE_PLAN §3d) exists,
and against a real serial-stream device if one becomes available -- everything
confirmed so far is the storage/flash path on one HID device.

## New TODO (not yet done)

A 5-10 minute recording, finger held on the probe throughout, to see how the
T6 sliding-window offset behaves once a session spans more than one reply.
Needs someone at the physical device for several minutes -- not a scriptable
read-only step like the probes so far. Recorded in RELEASE_PLAN §3d; will
follow up through `handoff/` when it exists.

## Windows mock question

Still open -- psytrap wants more detail before deciding; will follow up
separately. Treat as theory-only for now, per your stated default.
