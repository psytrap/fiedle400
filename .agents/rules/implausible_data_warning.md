# Rule: Alert on Implausible Oximetry / Probe-Out Data

## Trigger
- Always active when reporting, analyzing, or presenting PO-400 session downloads or data.

## Guidelines & Enforcement
1. **Detect Implausible Dummy Patterns**: Whenever downloaded or analyzed PO-400 session data contains constant dummy fallback values (e.g., 95% SpO2 / 64 BPM or 99% SpO2 / 95 BPM) accompanied by probe-out markers (`probe-out` status, or the out-of-range sentinels SpO2 127 / pulse 255; older stream devices use flags `0x30`, `0x10`, `0x0F`, `searching`), the agent **MUST START SCREAMING** using a high-visibility GitHub `[!WARNING]` alert block.
2. **Never Claim Success on Dummy Data**: DO NOT report dummy probe-out fallback values as valid physiological data or successful recording sessions.
3. **Explicit Call-to-Action**: Explicitly state that the sensor probe was idle/unattached during recording and instruct the user to record a new session with a finger attached to the probe.
