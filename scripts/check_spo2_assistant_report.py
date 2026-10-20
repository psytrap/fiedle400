#!/usr/bin/env python3
"""Compare a real SpO2 Assistant report (its XML export) with a probe's predictions.

Usage:
    python3 scripts/check_spo2_assistant_report.py REPORT.xml EXPECTED.json [--variant KEY]

REPORT.xml is the XML the program saves with a report ("Bericht"); EXPECTED.json is what a
probe script wrote (scripts/make_desat_probe.py, scripts/make_pulse_basal_probe.py). Without
--variant the run must use the default analysis parameters and every predicted value the
report has is compared; with --variant (a key of a "..._with_other_params" entry, e.g.
"drop=3" or "pulse change=5") only that parameter may differ from the defaults and only
the event count it predicts is compared. The program prints one decimal, so a value matches
when the prediction rounds to it. Prints a Markdown table for the ticket; exit code 1 when
anything differs or the run's parameters are not the expected ones.
See SPO2_ASSISTANT_CHECKS.md (T-036). This script only reads files.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET

# Report XML layout, from the writer's format strings in SpO2.exe (0x61bb20-0x61c444):
# <diagnosis><analy_result><event>{totle,time,avg,index,artifact,artifact_index}/{spo2,pulse}
# </event><spo2>{basal,time_low,event_low,min,event_min_avg,event_min_avg_low}</spo2>
# <pulse>{avg,min}</pulse></analy_result><analy_para><spo2>{drop,min_time,max_time,
# oscillation,max_avg,criteria}</spo2><pulse>{drop,time}</pulse></analy_para></diagnosis>
REPORT_VALUES = {
    # expected.json summary key: (XML path under analy_result, factor to report units)
    "total_event": ("event/totle/spo2", 1),
    "spo2_total_event": ("event/totle/spo2", 1),
    "index_per_hr": ("event/index/spo2", 1),
    "adjusted_index_per_hr": ("event/artifact_index/spo2", 1),
    "avg_low_spo2": ("spo2/event_min_avg", 1),
    "min_spo2": ("spo2/min", 1),
    "time_below_88_s": ("spo2/time_low", 1 / 60),  # the report shows minutes
    "basal_spo2_decoded": ("spo2/basal", 1),
    "pulse_total_event": ("event/totle/pulse", 1),
    "pulse_index_per_hr": ("event/index/pulse", 1),
    "pulse_avg_event_duration_s": ("event/avg/pulse", 1),
}

DEFAULT_PARAMS = {"spo2/drop": 4, "spo2/min_time": 10, "spo2/max_time": 180, "spo2/oscillation": 1,
                  "spo2/max_avg": 2, "spo2/criteria": 88, "pulse/drop": 6, "pulse/time": 8}
VARIANT_PARAMS = {"drop": "spo2/drop", "min_time": "spo2/min_time",
                  "pulse change": "pulse/drop", "pulse time": "pulse/time"}
VARIANT_COUNTS = {"total_event_with_other_params": "event/totle/spo2",
                  "pulse_total_event_with_other_params": "event/totle/pulse"}


def read_report(path):
    """(analy_result element, {param path: int}) from a report XML file."""
    with open(path, "rb") as f:
        data = f.read()
    # The program builds the XML in UTF-16 strings; accept a UTF-16 file even though its
    # declaration says utf-8 (not seen yet, T-019 only read the files by eye).
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        data = data.decode("utf-16").split("?>", 1)[-1].encode("utf-8")
    root = ET.fromstring(data)
    result, para = root.find("analy_result"), root.find("analy_para")
    if result is None or para is None:
        raise ValueError(f"{path} has no <analy_result>/<analy_para>; is it a SpO2 Assistant report?")
    params = {}
    for key in DEFAULT_PARAMS:
        el = para.find(key)
        if el is not None and (el.text or "").strip():
            params[key] = int(el.text)
    return result, params


def _value(result, path):
    el = result.find(path)
    text = (el.text or "").strip() if el is not None else ""
    return float(text) if text else None


def variant_params(variant):
    """{"drop=3": ...} -> {"spo2/drop": 3}; "drop=3,min_time=8" sets both."""
    params = dict(DEFAULT_PARAMS)
    for part in variant.split(","):
        name, _, value = part.partition("=")
        if name.strip() not in VARIANT_PARAMS:
            raise ValueError(f"unknown parameter '{name.strip()}' in variant '{variant}'")
        params[VARIANT_PARAMS[name.strip()]] = int(value)
    return params


def compare(result, params, expected, variant=None):
    """Rows (what, predicted, actual, ok) and whether everything matched."""
    summary = expected["summary"]
    want = variant_params(variant) if variant else DEFAULT_PARAMS
    rows = []
    for key, value in want.items():
        got = params.get(key)
        rows.append((f"parameter {key}", value, got, got == value))
    if variant:
        checks = [(f"{group}[{variant}]", summary[group][variant], path, 1)
                  for group, path in VARIANT_COUNTS.items() if variant in summary.get(group, {})]
        if not checks:
            raise ValueError(f"expected.json has no prediction for variant '{variant}'")
    else:
        checks = [(key, summary[key], path, factor)
                  for key, (path, factor) in REPORT_VALUES.items() if key in summary]
    for name, predicted, path, factor in checks:
        actual = _value(result, path)
        shown = round(predicted * factor, 1)
        rows.append((f"{name} ({path})", shown, actual, actual is not None and abs(shown - actual) < 0.05))
    return rows, all(r[3] for r in rows)


def markdown(rows):
    out = ["| Value | Predicted | Actual | Result |", "| :--- | :---: | :---: | :--- |"]
    for name, predicted, actual, ok in rows:
        out.append(f"| {name} | {predicted} | {'--' if actual is None else actual} | {'Match' if ok else '**Differs**'} |")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report", help="report XML saved by SpO2 Assistant")
    parser.add_argument("expected", help="expected.json written by a probe script")
    parser.add_argument("--variant", help='parameter variant from expected.json, e.g. "drop=3"')
    args = parser.parse_args(argv)
    try:
        result, params = read_report(args.report)
        with open(args.expected, encoding="utf-8") as f:
            expected = json.load(f)
        rows, ok = compare(result, params, expected, args.variant)
    except (OSError, ValueError, KeyError, ET.ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(markdown(rows))
    print("\nAll values match." if ok else "\nDifferences found; list each one in the ticket.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
