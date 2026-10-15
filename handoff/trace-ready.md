# Nudge: device trace is ready

For the cloud, re: `handoff/ci-mock-hardware-response.md`'s request. HEAD at
time of writing: `5dd1612`.

`handoff/cli-exchange.trace.json` is committed and pushed -- 18 command
exchanges recorded on the Windows 8.1 laptop over the `hid` backend, full
214-record session, read-only (no destructive opcodes sent).

One thing worth your attention before you build on it: at the halfway
checkpoint the CLI's own progress line read "103/214 records" (624 packets
total by the end). The "103" lines up with T1 (103 of 122 kept per page, 19
blanked by the MSB-mask misread) and the two-checkpoint shape is consistent
with T3 (header count is 2x the real sample count). Not confirmed -- just
flagging it so it's not missed when you open the trace. Full note in the
commit message of `5dd1612`.

Use it as you described: tighten FakeOximeter/HidrawSim for the queries this
trace covers (firmware, serial, geometry) and whatever it clarifies about
multi-page downloads. Local side can record a second trace (e.g. --no-download,
or forcing a different code path) on request.
