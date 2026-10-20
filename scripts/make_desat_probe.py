#!/usr/bin/env python3
"""Write a synthetic .SpO2 probe recording for checking SpO2 Assistant's event detection.

Usage:
    python3 scripts/make_desat_probe.py [OUTDIR]     # default: current directory

Writes probe-desat.SpO2 (open it in SpO2 Assistant), probe-desat.csv (the same series) and
expected.json (what the algorithm decoded in SPO2_FORMAT.md §7.2 predicts, per case and in
total). Pulse is a constant 70 bpm, so no pulse events are expected. See T-019.
"""

import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fiedle400.export import build_spo2_binary  # noqa: E402

BASE = 97
HR = 70
GAP = 120
PROBE_OUT = 127  # 0x7F sentinel
START = datetime(2026, 10, 20, 22, 0, 0)


def build_series():
    s, cases = [], []

    def flat(n, v=BASE):
        s.extend([v] * n)

    def descent(depth, dur):
        # Fall `depth` % in exactly `dur` samples, first step immediately, nadir on the last.
        start = s[-1]
        for k in range(1, dur + 1):
            s.append(start - -(-depth * k // dur))

    def recover():
        v = s[-1]
        while v < BASE:
            v += 1
            s.append(v)

    def case(name, expect, fn, note):
        flat(GAP)
        i0 = len(s)
        fn()
        recover()
        cases.append(dict(name=name, start_s=i0, end_s=len(s), expect=expect, note=note))

    def merge(rebound):
        descent(2, 6)
        s.append(s[-1] + rebound)
        descent(4, 6)

    def probe_out():
        descent(2, 6)
        s.append(PROBE_OUT)
        s.append(s[-2])
        descent(3, 6)

    def plateau():
        descent(4, 6)
        flat(6, s[-1])

    def below():
        descent(12, 24)
        flat(120, s[-1])

    flat(60)
    case("A", "event", lambda: descent(4, 12), "4 % over 12 s: plain event")
    case("B", "none", lambda: descent(3, 12), "3 % over 12 s: too shallow (event if drop = 3)")
    case("C", "none", lambda: descent(4, 8), "4 % over 8 s: too short (event if min duration = 8)")
    case("D", "event", lambda: descent(4, 10), "4 % over exactly 10 s: lower duration boundary")
    case("E", "none", lambda: descent(5, 9), "5 % over 9 s: one second too short")
    case("F", "event", lambda: descent(23, 12), "23 % over 12 s: steep, slope 1 %/s (integer) -> accepted")
    case("G", "none", lambda: descent(25, 12), "25 % over 12 s: slope 2 %/s -> rejected as too steep")
    case("H", "event", lambda: descent(6, 170), "6 % over 170 s: long but within 180 s")
    case("I", "none", lambda: descent(6, 200), "6 % over 200 s: longer than 180 s")
    case("J", "event", lambda: merge(1), "2 % in 6 s, rebound +1 %, 4 % in 6 s: merged into one event")
    case("K", "none", lambda: merge(2), "same with rebound +2 %: not merged, both parts too short")
    case("L", "none", probe_out, "5 % fall split by one probe-out sample: breaks the event")
    case("M", "event", plateau, "4 % in 6 s then 6 s flat at the nadir: flat counts (12 s) -> event")
    case("N", "event", below, "12 % in 24 s to 85 %, hold 120 s: event, and time below 88 %")
    flat(GAP)
    return s, cases


def detect(x, drop=4, min_time=10, max_time=180, max_avg=2, oscillation=1, lo=0, hi=100):
    """The detector decoded from SpO2.exe (SPO2_FORMAT.md §7.2). Returns [start, nadir, from, to]."""
    cands = []
    st = en = 0

    def finish():
        nonlocal st, en
        if st and en and en - st > 0:
            cands.append([st, en, x[st], x[en]])
        st = en = 0

    for i, v in enumerate(x):
        if v > hi or v < lo:
            finish()
            continue
        if i == 0:
            continue
        p = x[i - 1]
        if v > p:
            finish()
        elif v == p:
            if st:
                en = i
        elif st:
            en = i
        elif lo < p < hi:
            st, en = i - 1, i
    finish()

    def accepted(c):
        dur, depth = c[1] - c[0], c[2] - c[3]
        return (dur and depth >= drop and min_time <= dur <= max_time and depth // dur < max_avg
                and all(lo <= x[k] <= hi for k in range(c[0], c[1] + 1)))

    events = []
    if not cands:
        return events
    cur = cands[0][:]
    for n in cands[1:]:
        if n[2] - cur[3] <= oscillation and n[3] < cur[3] and n[2] < cur[2] and n[0] - cur[1] <= min_time:
            cur[1], cur[3] = n[1], n[3]
        else:
            if accepted(cur):
                events.append(cur)
            cur = n[:]
    if accepted(cur):
        events.append(cur)
    return events


def main(argv):
    outdir = argv[1] if len(argv) > 1 else "."
    s, cases = build_series()
    events = detect(s)
    for c in cases:
        got = [e for e in events if c["start_s"] - 1 <= e[0] < c["end_s"]]
        c["predicted"] = "event" if got else "none"
        c["events"] = [dict(start_s=e[0], nadir_s=e[1], from_pct=e[2], to_pct=e[3]) for e in got]
        assert c["predicted"] == c["expect"], c
    valid = [v for v in s if 1 <= v <= 100]
    summary = dict(
        samples=len(s),
        duration_min=round(len(s) / 60, 2),
        total_event=len(events),
        index_per_hr=round(len(events) / (len(s) / 3600), 2),
        adjusted_index_per_hr=round(len(events) / (len(valid) / 3600), 2),
        basal_spo2_mean=round(sum(valid) / len(valid), 2),
        avg_low_spo2=round(sum(e[3] for e in events) / len(events), 2),
        min_spo2=min(valid),
        time_below_88_s=sum(1 for v in valid if v < 88),
        artifact_samples=len(s) - len(valid),
        total_event_with_other_params={
            "drop=3": len(detect(s, drop=3)),
            "min_time=8": len(detect(s, min_time=8)),
            "drop=3,min_time=8": len(detect(s, drop=3, min_time=8)),
        },
    )
    recs = [dict(spo2=None if v == PROBE_OUT else v, heart_rate=None if v == PROBE_OUT else HR)
            for v in s]
    with open(os.path.join(outdir, "probe-desat.SpO2"), "wb") as f:
        f.write(build_spo2_binary(recs, START))
    with open(os.path.join(outdir, "probe-desat.csv"), "w") as f:
        f.write("second,spo2,pulse\n")
        for i, v in enumerate(s):
            f.write(f"{i},{'' if v == PROBE_OUT else v},{'' if v == PROBE_OUT else HR}\n")
    with open(os.path.join(outdir, "expected.json"), "w") as f:
        json.dump(dict(start=START.isoformat(), summary=summary, cases=cases), f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
