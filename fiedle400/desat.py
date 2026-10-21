"""SpO2 desaturation events and the report values derived from them.

Implements the detector decoded from SpO2 Assistant (SPO2_FORMAT.md §7.2) and
validated against the real program with the T-019 probe recording: the same
event counts for the default parameters and for two changed ones. Samples are
taken as 1 Hz, as in the `.spo2` format: every neighbouring pair is one second apart, so
a recording with a pause in it (several stored sessions) must be padded to one entry per
second first, `export.pad_records` (T-022).

Basal SpO2 is the mean of the valid samples outside the event descents (start to
nadir), decoded from SpO2.exe in T-031 (SPO2_FORMAT.md §7.1). The program runs
the same detector on the pulse rate with its own parameters (T-029, §7.3);
`detect_pulse_events` gives those events and `summarize_pulse` their report values (T-030).
The decoded algorithm has not yet been checked in the real program (T-035).
"""

DROP = 4          # Percent Drop For Event (%)
MIN_TIME = 10     # Minimum Event Duration (s)
MAX_TIME = 180    # fixed in SpO2 Assistant
MAX_AVG = 2       # fixed: average fall must stay below this (%/s)
OSCILLATION = 1   # fixed: rebound (%) tolerated when joining partial descents
CRITERIA = 88     # desaturation criteria level for the "below" counts (%)
LO, HI = 0, 100   # a sample outside this range breaks an event
INVALID = 127     # probe-out sentinel, used for missing readings

PULSE_DROP = 6        # Pulse change for event (bpm), UI range 2-20
PULSE_MIN_TIME = 8    # Minimum pulse event duration (s)
PULSE_HI = 254        # pulse valid range is 0..254; the 255 sentinel breaks an event
PULSE_INVALID = 255


def detect_events(spo2, drop=DROP, min_time=MIN_TIME):
    """Return the accepted events as dicts: start, nadir (sample indices),
    from_pct, to_pct. `spo2` is a list of ints; None counts as probe-out."""
    return _detect(spo2, drop, min_time, HI, INVALID)


def detect_pulse_events(pulse, drop=PULSE_DROP, min_time=PULSE_MIN_TIME):
    """Pulse-rate events: the same detector on the pulse series (SpO2.exe builds a
    second instance at 0x532b39 with these values), so an event is a *fall* of at
    least `drop` bpm over `min_time`..180 s; a rise is never one. Same dict keys as
    detect_events (from_pct/to_pct hold bpm). None counts as probe-out."""
    return _detect(pulse, drop, min_time, PULSE_HI, PULSE_INVALID)


def _detect(series, drop, min_time, hi, invalid):
    x = [invalid if v is None else v for v in series]
    cands = []
    st = en = 0

    def finish():
        nonlocal st, en
        if st and en and en - st > 0:
            cands.append([st, en, x[st], x[en]])
        st = en = 0

    for i, v in enumerate(x):
        if v > hi or v < LO:
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
        elif LO < p < hi:
            st, en = i - 1, i
    finish()

    def accepted(c):
        dur, depth = c[1] - c[0], c[2] - c[3]
        return bool(
            dur
            and depth >= drop
            and min_time <= dur <= MAX_TIME
            and depth // dur < MAX_AVG
            and all(LO <= x[k] <= hi for k in range(c[0], c[1] + 1))
        )

    events = []
    if not cands:
        return events
    cur = cands[0][:]
    for n in cands[1:]:
        if n[2] - cur[3] <= OSCILLATION and n[3] < cur[3] and n[2] < cur[2] and n[0] - cur[1] <= min_time:
            cur[1], cur[3] = n[1], n[3]
        else:
            if accepted(cur):
                events.append(cur)
            cur = n[:]
    if accepted(cur):
        events.append(cur)
    return [dict(start=e[0], nadir=e[1], from_pct=e[2], to_pct=e[3]) for e in events]


def summarize(spo2, events, criteria=CRITERIA):
    """Report values for a recording, named as in SpO2 Assistant's report."""
    valid = [i for i, v in enumerate(spo2) if v is not None and 1 <= v <= 100]
    out = dict(samples=len(spo2), valid_samples=len(valid), total_event=len(events))
    if not spo2:
        return out
    hours = len(spo2) / 3600.0
    out["index_per_hr"] = round(len(events) / hours, 2)
    out["adjusted_index_per_hr"] = round(len(events) / (len(valid) / 3600.0), 2) if valid else None
    out["artifact_pct"] = round(100.0 * (len(spo2) - len(valid)) / len(spo2), 2)
    out["avg_low_spo2"] = round(sum(e["to_pct"] for e in events) / len(events), 2) if events else None
    low = [e for e in events if e["to_pct"] < criteria]
    out["events_below_criteria"] = len(low)
    out["avg_low_spo2_below_criteria"] = round(sum(e["to_pct"] for e in low) / len(low), 2) if low else None
    # "Time (min) <criteria" (SPO2_FORMAT.md Sec7.1), same valid samples as the rest of
    # this report -- not a separately-filtered count (T-044).
    out["time_below_criteria_s"] = sum(1 for i in valid if spo2[i] < criteria)
    out["avg_event_duration_s"] = (
        round(sum(e["nadir"] - e["start"] for e in events) / len(events), 1) if events else None
    )
    inside = set()
    for e in events:
        inside.update(range(e["start"], e["nadir"] + 1))
    # SpO2.exe 0x54ced1-0x54d059: (sum of valid samples - sum over every event's
    # start..nadir) / (valid count - those samples); not computed when nothing is left.
    basal = [spo2[i] for i in valid if i not in inside]
    out["basal_spo2"] = round(sum(basal) / len(basal), 2) if basal else None
    return out


def summarize_pulse(pulse, events):
    """Pulse-channel report values (SPO2_FORMAT.md §7.1/§7.3; same formulas as `summarize`).
    Valid pulse is 1..250 like the rest of fiedle400, while the detector's own range is
    0..254; the program's artifact count may differ at the margins (T-035)."""
    valid = sum(1 for v in pulse if v is not None and 1 <= v <= 250)
    out = dict(samples=len(pulse), valid_samples=valid, total_event=len(events))
    if not pulse:
        return out
    out["index_per_hr"] = round(len(events) / (len(pulse) / 3600.0), 2)
    out["adjusted_index_per_hr"] = round(len(events) / (valid / 3600.0), 2) if valid else None
    out["artifact_pct"] = round(100.0 * (len(pulse) - valid) / len(pulse), 2)
    out["avg_event_duration_s"] = (
        round(sum(e["nadir"] - e["start"] for e in events) / len(events), 1) if events else None
    )
    return out
