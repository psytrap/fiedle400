# T-055: Ship a synthetic demo recording in the Windows installer

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `scripts/make_demo_recording.py` (new)
  - `packaging/windows/demo.SpO2` (new, generated)
  - `packaging/windows/fiedle400.iss`
  - `PACKAGING.md`

---

## Description & Context

Direct instruction from psytrap: add a `demo.spo2` to the Windows installer, so
a first-run user has something to open in `fiedle400 view` without the device
attached. Related to [T-054](T-054-readme-demo-screen-capture.md)'s
README screen capture, but a separate, smaller piece of work with its own file
to generate and its own installer wiring -- not folded into T-054.

Per the project's rule against shipping real captures as demo/test fixtures
(`.agents/rules/implausible_data_warning.md`), the file had to be synthetic, not
a real stored recording.

---

## Criteria

- [x] A synthetic `.SpO2` generator script exists, producing a short, clean
      trace with at least one visible SpO2 desaturation event
- [x] Generated file is wired into `packaging/windows/fiedle400.iss`, installed
      to the user's recordings folder (not just sitting unused in `{app}`)
- [x] A way to open it is discoverable (Start Menu entry), not just a file
      dropped silently into a folder
- [x] `PACKAGING.md` documents the new file and how to regenerate it
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

**2026-10-21:** Wrote `scripts/make_demo_recording.py` (hwsim-style synthetic
generator, no real device data): a ~9-minute trace with small natural
wander plus two scripted SpO2 desaturation events, one with a co-occurring
pulse-rate fall (apnea-style CVHR, see the pulse-events discussion earlier
this session). Verified against `fiedle400.desat.detect_events`/
`detect_pulse_events`: 2 SpO2 events and 3 pulse events actually fire (the
extra pulse events come from the random-walk padding occasionally
qualifying on its own -- harmless, still looks organic for a demo). Output:
`packaging/windows/demo.SpO2`, 548 samples, 2180 bytes.

Wired into `fiedle400.iss`: new `#define DemoSpo2 "demo.SpO2"`, a `[Files]`
line installing it to `{userdocs}\PO-400` (`onlyifdoesntexist
uninsneveruninstall`, so a re-run/upgrade never clobbers a same-named real
file and uninstall never deletes it), and a new Start Menu entry "View Demo
Recording" running `fiedle400.exe view "<path>\demo.SpO2"` (confirmed `view`
is the right subcommand from T-013's implementation in `cli.py`).

`PACKAGING.md`'s Windows section updated with a bullet describing the demo
file and pointing at the regeneration script. Full suite re-run after the
change: 401 tests, OK (skipped=7) -- no regressions.

Not done (out of scope for a direct-instruction ticket): no real Inno Setup
build was run (`ISCC` not available in this Linux session) to confirm the
`.iss` compiles cleanly -- that's covered by the existing CI build-release
workflow and T-047's eventual G5/G6 Windows pass.
