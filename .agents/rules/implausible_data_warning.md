# Rule: Alert on Implausible Oximetry / Probe-Out Data

## Trigger
- Always active when reporting, analyzing, or presenting PO-400 session downloads or data.

## Guidelines & Enforcement
1. **Detect implausible data**: constant values over a long stretch (e.g. 95% SpO2 / 64 BPM or 99% SpO2 / 95 BPM), out-of-range values (SpO2 127 / pulse 255, the sentinels the vendor tool writes for decoded values outside the valid range), or a `probe-out` status. No real recording has shown a finger-out stretch yet (T1, CHANGELOG.md), so treat any of these as a sign the probe was off, not as a known device pattern. The live-stream status names (`probe-out`, `searching`) come from the decoder in `fiedle400/protocol/decompression.py`, not from a recording.
2. **Warn first**: the report **MUST** open with a GitHub `[!WARNING]` alert block naming what was found.
3. **Never claim success on such data**: do not report it as valid physiological data or a successful recording session.
4. **Explicit call to action**: state that the probe was probably idle or unattached during recording and ask the user to record a new session with a finger on the probe.
