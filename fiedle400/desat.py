"""SpO2 desaturation events and the report values derived from them.

Implements the detector decoded from SpO2 Assistant (SPO2_FORMAT.md §7.2) and
validated against the real program with the T-019 probe recording: the same
event counts for the default parameters and for two changed ones. Samples are
taken as 1 Hz, as in the `.spo2` format.

Basal SpO2 is the one value that is not confirmed: the plain mean of the valid
samples reads about 0.8 points lower than the real program's figure on the
probe. `basal_spo2` uses the mean outside the event descents, which matches the
probe's figure to the printed precision, but the vendor's exact rule is not
decoded (SPO2_FORMAT.md §7.1).
"""

DROP = 4          # Percent Drop For Event (%)
MIN_TIME = 10     # Minimum Event Duration (s)
MAX_TIME = 180    # fixed in SpO2 Assistant
MAX_AVG = 2       # fixed: average fall must stay below this (%/s)
OSCILLATION = 1   # fixed: rebound (%) tolerated when joining partial descents
CRITERIA = 88     # desaturation criteria level for the "below" counts (%)
LO, HI = 0, 100   # a sample outside this range breaks an event
INVALID = 127     # probe-out sentinel, used for missing readings


def detect_events(spo2, drop=DROP, min_time=MIN_TIME):
    """Return the accepted events as dicts: start, nadir (sample indices),
    from_pct, to_pct. `spo2` is a list of ints; None counts as probe-out."""
    x = [INVALID if v is None else v for v in spo2]
    cands = []
    st = en = 0

    def finish():
        nonlocal st, en
        if st and en and en - st > 0:
            cands.append([st, en, x[st], x[en]])
        st = en = 0

    for i, v in enumerate(x):
        if v > HI or v < LO:
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
        elif LO < p < HI:
            st, en = i - 1, i
    finish()

    def accepted(c):
        dur, depth = c[1] - c[0], c[2] - c[3]
        return bool(
            dur
            and depth >= drop
            and min_time <= dur <= MAX_TIME
            and depth // dur < MAX_AVG
            and all(LO <= x[k] <= HI for k in range(c[0], c[1] + 1))
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
    out["avg_event_duration_s"] = (
        round(sum(e["nadir"] - e["start"] for e in events) / len(events), 1) if events else None
    )
    inside = set()
    for e in events:
        inside.update(range(e["start"], e["nadir"] + 1))
    basal = [spo2[i] for i in valid if i not in inside] or [spo2[i] for i in valid]
    out["basal_spo2"] = round(sum(basal) / len(basal), 2) if basal else None
    return out
