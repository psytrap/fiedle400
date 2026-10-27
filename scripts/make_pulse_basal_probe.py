#!/usr/bin/env python3
"""Write a synthetic .SpO2 probe for checking two decodes in the real SpO2 Assistant (T-035).

Usage:
    python3 scripts/make_pulse_basal_probe.py [OUTDIR]     # default: current directory

Writes probe-pulse-basal.SpO2 (open it in SpO2 Assistant), probe-pulse-basal.csv (the
same series) and expected.json (predictions). Two parts:

1. SpO2: a plain event, a long deep one, then a 12 % fall into a 10-minute hold at 85 %
   that is no event (too long: the flat samples count as part of the descent). The
   candidate Basal SpO2 rules now give clearly different numbers: the decoded rule
   (mean of valid samples outside event falls, T-031) keeps the hold and drops the
   events, a "samples >= 88 %" rule drops the hold, the plain mean keeps everything.
2. Pulse rate (SpO2 flat): falls and rises around 70 bpm that the decoded pulse-event
   detector (T-029: the SpO2 detector on the pulse series, 6 bpm / 8 s) accepts or rejects,
   including a rise, which is never an event.
"""

import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fiedle400.desaturation import detect_events, detect_pulse_events, summarize  # noqa: E402
from fiedle400.export import build_spo2_binary  # noqa: E402

SPO2 = 97
HR = 70
GAP = 120
START = datetime(2026, 10, 21, 22, 0, 0)


def _steps(start, delta, dur):
    """`dur` samples moving `delta` from `start`, first step immediately, target on the last."""
    sign = 1 if delta > 0 else -1
    return [start + sign * -(-abs(delta) * k // dur) for k in range(1, dur + 1)]


def build_series():
    spo2, pulse, cases = [], [], []

    def flat(n, s=None, p=None):
        spo2.extend([spo2[-1] if s is None and spo2 else (s or SPO2)] * n)
        pulse.extend([pulse[-1] if p is None and pulse else (p or HR)] * n)

    def spo2_move(delta, dur):
        spo2.extend(_steps(spo2[-1], delta, dur))
        pulse.extend([HR] * dur)

    def pulse_move(delta, dur):
        pulse.extend(_steps(pulse[-1], delta, dur))
        spo2.extend([SPO2] * dur)

    def spo2_recover():
        while spo2[-1] < SPO2:
            spo2_move(1, 1)

    def pulse_recover():
        while pulse[-1] != HR:
            pulse_move(1 if pulse[-1] < HR else -1, 1)

    def case(channel, name, expect, fn, note):
        flat(GAP, SPO2, HR)
        i0 = len(spo2)
        fn()
        (spo2_recover if channel == "spo2" else pulse_recover)()
        cases.append(dict(channel=channel, name=name, start_s=i0, end_s=len(spo2), expect=expect, note=note))

    def probe_out_split():
        pulse_move(-3, 5)
        spo2.append(None)
        pulse.append(None)
        spo2.append(SPO2)
        pulse.append(pulse[-2])
        pulse_move(-4, 5)

    def merge():
        pulse_move(-3, 5)
        pulse_move(1, 1)
        pulse_move(-5, 5)

    def rise():
        pulse_move(10, 10)
        flat(20, SPO2, None)
        pulse_move(-10, 4)  # back down in 4 s: too short and too steep for an event

    def hold():
        spo2_move(-12, 6)
        flat(600, None, HR)  # flat samples extend the descent: 606 s > 180 s, so no event

    flat(60, SPO2, HR)
    case("spo2", "S1", "event", lambda: spo2_move(-4, 12), "4 % over 12 s: plain SpO2 event")
    case("spo2", "S2", "event", lambda: spo2_move(-25, 175), "25 % over 175 s: long deep event, left out of the decoded Basal")
    case("spo2", "S3", "none", hold, "12 % in 6 s, then 10 min at 85 %: the flat part makes it longer than 180 s, no event")
    case("pulse", "P1", "event", lambda: pulse_move(-6, 10), "pulse -6 bpm over 10 s: event")
    case("pulse", "P2", "none", lambda: pulse_move(-5, 10), "-5 bpm over 10 s: too small (event if pulse change = 5)")
    case("pulse", "P3", "none", lambda: pulse_move(-6, 7), "-6 bpm over 7 s: too short (event if pulse time = 7)")
    case("pulse", "P4", "event", lambda: pulse_move(-6, 8), "-6 bpm over exactly 8 s: lower duration boundary")
    case("pulse", "P5", "event", lambda: pulse_move(-19, 10), "-19 bpm over 10 s: 1 bpm/s (integer) -> accepted")
    case("pulse", "P6", "none", lambda: pulse_move(-20, 10), "-20 bpm over 10 s: 2 bpm/s -> rejected as too steep")
    case("pulse", "P7", "none", rise, "+10 bpm over 10 s, back in 4 s: a rise is never an event")
    case("pulse", "P8", "none", lambda: pulse_move(-8, 200), "-8 bpm over 200 s: longer than 180 s")
    case("pulse", "P9", "event", merge, "-3 in 5 s, +1 rebound, -5 in 5 s: merged into one event")
    case("pulse", "P10", "none", probe_out_split, "-3 then -4 split by one probe-out second: breaks the event")
    flat(GAP, SPO2, HR)
    return spo2, pulse, cases


def predict(spo2, pulse, cases):
    events = detect_events(spo2)
    pevents = detect_pulse_events(pulse)
    for c in cases:
        evs = events if c["channel"] == "spo2" else pevents
        got = [e for e in evs if c["start_s"] - 1 <= e["start"] < c["end_s"]]
        c["predicted"] = "event" if got else "none"
        c["events"] = [dict(start_s=e["start"], nadir_s=e["nadir"], from_value=e["from_pct"], to_value=e["to_pct"])
                       for e in got]
        assert c["predicted"] == c["expect"], c
    valid = [v for v in spo2 if v is not None]
    vpulse = [v for v in pulse if v is not None]
    s = summarize(spo2, events)
    return dict(
        samples=len(spo2),
        duration_min=round(len(spo2) / 60, 2),
        spo2_total_event=len(events),
        basal_spo2_decoded=round(s["basal_spo2"], 1),
        basal_spo2_if_mean_of_samples_at_or_above_88=round(sum(v for v in valid if v >= 88) / sum(1 for v in valid if v >= 88), 1),
        basal_spo2_if_plain_mean=round(sum(valid) / len(valid), 1),
        time_below_88_s=sum(1 for v in valid if v < 88),
        pulse_total_event=len(pevents),
        pulse_total_event_with_other_params={
            "pulse change=5": len(detect_pulse_events(pulse, drop=5)),
            "pulse time=7": len(detect_pulse_events(pulse, min_time=7)),
        },
        pulse_index_per_hr=round(len(pevents) / (len(pulse) / 3600), 1),
        pulse_avg_event_duration_s=round(sum(e["nadir"] - e["start"] for e in pevents) / len(pevents), 1),
        pulse_plain_mean_bpm=round(sum(vpulse) / len(vpulse), 1),
        pulse_min_bpm=min(vpulse),
    )


def main(argv):
    outdir = argv[1] if len(argv) > 1 else "."
    spo2, pulse, cases = build_series()
    summary = predict(spo2, pulse, cases)
    recs = [dict(spo2=s, heart_rate=p) for s, p in zip(spo2, pulse)]
    with open(os.path.join(outdir, "probe-pulse-basal.SpO2"), "wb") as f:
        f.write(build_spo2_binary(recs, START))
    with open(os.path.join(outdir, "probe-pulse-basal.csv"), "w") as f:
        f.write("second,spo2,pulse\n")
        for i, (s, p) in enumerate(zip(spo2, pulse)):
            f.write(f"{i},{'' if s is None else s},{'' if p is None else p}\n")
    with open(os.path.join(outdir, "expected.json"), "w") as f:
        json.dump(dict(start=START.isoformat(), summary=summary, cases=cases), f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
