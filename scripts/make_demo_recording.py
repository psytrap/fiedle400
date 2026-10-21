#!/usr/bin/env python3
"""Write demo.SpO2, a short synthetic recording shipped with the Windows installer (T-055).

Usage:
    python3 scripts/make_demo_recording.py [OUTDIR]     # default: packaging/windows

Purely synthetic (hwsim-style, no real device data -- RELEASE_PLAN rule against
shipping real captures): a ~12-minute trace with gentle natural variation plus two
SpO2 desaturation events (one plain, one with a co-occurring pulse-rate fall, per
SPO2_FORMAT.md Sec7.2/7.3) so a first-run user has something to open in
`fiedle400 view` without a device attached.
"""

import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fiedle400.export import build_spo2_binary  # noqa: E402

BASE_SPO2 = 97
BASE_HR = 68
START = datetime(2026, 10, 21, 23, 30, 0)


def _wander(start, n, lo, hi, seed):
    """n samples of `start` with small pseudo-random steps, clamped to [lo, hi]."""
    out = [start]
    state = seed
    for _ in range(n - 1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        step = (state % 3) - 1  # -1, 0, or +1
        out.append(max(lo, min(hi, out[-1] + step)))
    return out


def _descent(series, depth, dur):
    start = series[-1]
    for k in range(1, dur + 1):
        series.append(start - -(-depth * k // dur))


def _recover(series, target):
    while series[-1] < target:
        series.append(series[-1] + 1)


def build():
    spo2 = _wander(BASE_SPO2, 180, 95, 98, seed=42)
    hr = _wander(BASE_HR, 180, 64, 72, seed=7)

    # Plain SpO2 desaturation event: 5 % fall over 15 s, pulse unaffected.
    _descent(spo2, 5, 15)
    spo2.extend([spo2[-1]] * 20)
    _recover(spo2, BASE_SPO2)
    hr.extend(_wander(hr[-1], len(spo2) - len(hr), 64, 72, seed=13))

    pad = _wander(spo2[-1], 150, 95, 98, seed=99)
    spo2.extend(pad[1:])
    hr.extend(_wander(hr[-1], len(spo2) - len(hr), 64, 72, seed=21))

    # Second event: SpO2 fall with a co-occurring pulse-rate fall (apnea-style CVHR).
    _descent(spo2, 8, 20)
    spo2.extend([spo2[-1]] * 10)
    _recover(spo2, BASE_SPO2)
    _descent(hr, 10, 12)
    hr.extend([hr[-1]] * 6)
    _recover(hr, BASE_HR)
    hr.extend(_wander(hr[-1], len(spo2) - len(hr), 64, 72, seed=55))

    tail = _wander(spo2[-1], 140, 95, 98, seed=77)
    spo2.extend(tail[1:])
    hr.extend(_wander(hr[-1], len(spo2) - len(hr), 64, 72, seed=88))

    return spo2, hr


def main(argv):
    outdir = argv[1] if len(argv) > 1 else os.path.join(ROOT, "packaging", "windows")
    spo2, hr = build()
    assert len(spo2) == len(hr)
    recs = [dict(spo2=s, heart_rate=h) for s, h in zip(spo2, hr)]
    path = os.path.join(outdir, "demo.SpO2")
    with open(path, "wb") as f:
        f.write(build_spo2_binary(recs, START))
    print(f"wrote {path}: {len(recs)} samples ({len(recs) / 60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
