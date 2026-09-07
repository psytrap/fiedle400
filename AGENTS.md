# Workspace Rules

## Rule: Alert on Implausible Oximetry / Probe-Out Data

Whenever reporting, analyzing, or presenting PO-400 session downloads or oximetry data:
1. **Scream on Implausible Dummy Values**: If session data contains dummy probe-out values (e.g. constant 95% / 64 BPM or 99% / 95 BPM with status flags like `0x30`, `0x10`, `0x0F`, `probe-out`, or `searching`), YOU MUST IMMEDIATELY DISPLAY A GitHub `[!WARNING]` ALERT IN ALL CAPS!
2. **Never Claim Success**: DO NOT report dummy probe-out fallback values as valid physiological recordings.
3. **Call-to-Action**: Instruct the user to record a new session with a finger securely attached to the sensor probe.
