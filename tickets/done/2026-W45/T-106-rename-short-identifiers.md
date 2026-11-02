# T-106: Rename short identifiers that break the naming rule

- **Priority:** Low
- **Owner:** Cloud
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py`, `fiedle400/cli.py`, `fiedle400/protocol/manual.py`,
    `fiedle400/protocol/parsers.py`, `fiedle400/serial_port.py`
  - `.agents/rules/coding-conventions.md` (the rule, from [T-043](T-043-coding-conventions.md))

---

## Description & Context

Follow-up to T-043, which wrote the naming rule and deliberately renamed nothing.
`desaturation.py`, the case that prompted T-043, was already renamed locally
(`descent_start`, `descent_end`, `candidate`, ...).

A scan of `fiedle400/` on 2026-11-02 (assignments and parameters of one or two characters)
found these that the rule does not allow:

- `engine/device.py`: `sn`, `up` (serial number, user profile), `sq`, `s`, `r`.
- `cli.py`: `ow` (overwrite answer), parameter `fn`.
- `protocol/manual.py`: `op`, `p`, `s`.
- `protocol/parsers.py`: `yr`, `mo`, `dy`, `mi`, `sc`, `dp` (date parts; `hh`/`mm`/`ss`-style
  names that copy `PROTOCOL.md` may stay, see the rule).
- `serial_port.py`: `p`; the `H, D, P` ctypes aliases are a judgement call.

Allowed by the rule and not to be renamed: `m0`..`m2`, `b0`..`b3`, `cc`, `hr`, `ts`, `dt`,
`lo`/`hi`, loop indices.

psytrap, 2026-11-02: "apply the rules from t43".

---

## Criteria

- [x] One module per change, behaviour unchanged (pure renames).
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`) and pyflakes stays clean.

---

## Execution Notes

Done 2026-11-02 (cloud, patch 0039, same patch as T-043). psytrap first asked to apply the
rule ("apply the rules from t43"), then, after a first pass that only touched local variables:
"rename all. We fix it now".

- **Every identifier defined in `fiedle400/`** now follows the rule: locals, parameters,
  attributes, dataclass fields, functions and constants (about 280 project-wide renames with
  the `rope` refactoring library, which also updated every caller in `tests/` and `scripts/`,
  plus about 100 hand-picked names for one-letter loop and comprehension variables). Examples:
  `sess_info` -> `session_info`, `dev_path` -> `device_path`, `duration_str` -> `duration_text`,
  `calc_checksum_7bit` -> `calculate_checksum_7bit`, `HID_READ_TIMEOUT_SEC` ->
  `HID_READ_TIMEOUT_SECONDS`, `DEV_ROOT` -> `DEVICE_ROOT`, `s`/`e`/`f` -> `session`/`error`/`file`.
- `SessionInfo.duration_sec` (the stored field) became `stored_duration_seconds`, because
  `duration_seconds` is already the property that falls back to the record count.
- Strings that name code were updated too (`__all__`, `mock.patch` targets, `getattr` names,
  the internal `"rtc_time_str"` and `"base_val"` dictionary keys), as were comments and the
  code samples in `SPO2_FORMAT.md` and `RELEASE_PLAN.md`.
- Then psytrap: "fix it now" for what was left, and "Make sure HTML works then":
  - **Keys fiedle400 writes:** the CSV/JSON export column `seq` -> `sequence` (user-visible,
    in CHANGELOG), and the viewer's analysis keys (`from_pct` -> `from_percent`,
    `index_per_hr` -> `index_per_hour`, `artifact_pct` -> `artifact_percent`,
    `avg_low_spo2` -> `average_low_spo2`, `time_below_criteria_s` -> `time_below_criteria_seconds`,
    `avg_event_duration_s` -> `average_event_duration_seconds`, `params` -> `parameters`).
    Nothing reads these back from older files (`recording.py` reads only timestamp, SpO2,
    pulse and flags), so no compatibility code was needed.
  - **Viewer JavaScript and HTML ids:** every name spelled out (`fmtSec` -> `formatSeconds`,
    `EVT_HI` -> `EVENT_HIGH`, `PULSE_HI` -> `PULSE_HIGH`, `padL` -> `paddingLeft`,
    `dropPct` -> `dropPercent`, `minDur` -> `minimumTime`, canvas `c` -> `chart`, ...).
    Checked in headless Chromium on the demo recording: no script errors, and the statistics
    table, the recomputation after changing an event parameter, the tooltip and drag-zoom /
    reset give exactly the same results as before the rename.
  - **`tests/`:** about 750 locals, parameters, helper names and test-fixture attributes
    (`out` -> `output`, `rc` -> `exit_code`, `dev` -> `device`, one-letter names by meaning).
- **Not renamed:** keys that come from outside (hidapi's `manufacturer_string`, third-party CSV
  columns such as `pr`, the probe `expected.json` keys `scripts/check_spo2_assistant_report.py`
  reads from files already recorded), argparse attributes (they follow the CLI flags), names
  copied from outside sources and acronyms the rule allows, and `scripts/`. CHANGELOG and
  closed tickets keep the old names, since they describe the code as it was.
- No behaviour change. Full suite OK; pyflakes clean apart from the two known items (`readline`
  in `cli.py`, an unused `sys` in `tests/test_sync_patch.py` that predates this patch).
