"""SpO2 desaturation events and the report values derived from them.

An event's "nadir" is its lowest point: the sample where the value (SpO2 % or pulse
bpm) bottoms out before recovering, between the event's `start` and that point. Standard
pulse-oximetry/sleep-medicine term (e.g. "nadir SpO2" in a sleep study), not specific to
this codebase -- kept here since it isn't obvious to a reader coming from software rather
than that domain.

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
MAX_AVERAGE = 2       # fixed: average fall must stay below this (%/s)
OSCILLATION = 1   # fixed: rebound (%) tolerated when joining partial descents
CRITERIA = 88     # desaturation criteria level for the "below" counts (%)
LOW, HIGH = 0, 100   # a sample outside this range breaks an event
INVALID = 127     # probe-out sentinel, used for missing readings

PULSE_DROP = 6        # Pulse change for event (bpm), UI range 2-20
PULSE_MIN_TIME = 8    # Minimum pulse event duration (s)
PULSE_HIGH = 254        # pulse valid range is 0..254; the 255 sentinel breaks an event
PULSE_INVALID = 255


def detect_events(spo2, drop=DROP, min_time=MIN_TIME):
    """Return the accepted events as dicts: start, nadir (sample indices),
    from_percent, to_percent. `spo2` is a list of ints; None counts as probe-out."""
    return _detect(spo2, drop, min_time, HIGH, INVALID)


def detect_pulse_events(pulse, drop=PULSE_DROP, min_time=PULSE_MIN_TIME):
    """Pulse-rate events: the same detector on the pulse series (SpO2.exe builds a
    second instance at 0x532b39 with these values), so an event is a *fall* of at
    least `drop` bpm over `min_time`..180 s; a rise is never one. Same dict keys as
    detect_events (from_percent/to_percent hold bpm). None counts as probe-out."""
    return _detect(pulse, drop, min_time, PULSE_HIGH, PULSE_INVALID)


def _detect(series, drop, min_time, high, invalid):
    """Shared state machine behind detect_events/detect_pulse_events: walk the clamped
    series to find monotonic (or flat) descents, merge near-adjacent partial descents
    into a single candidate (the small-rebound/short-gap join SpO2 Assistant itself
    does), then keep only the candidates `_is_accepted_event` passes."""
    values = [invalid if value is None else value for value in series]
    candidates = _find_descent_candidates(values, high)
    return _merge_and_accept(candidates, values, drop, min_time, high)


def _find_descent_candidates(values, high):
    """One candidate per maximal run where the series falls or holds flat, as
    [start_index, nadir_index, value_at_start, value_at_nadir]. A probe-out/out-of-range
    sample (outside LO..hi) always breaks the current descent."""
    candidates = []
    # 0 doubles as "no descent currently open" (falsy): a descent that happens to start
    # at sample index 0 is therefore never recorded as a candidate here. That matches
    # SpO2 Assistant's own decompiled behavior -- not a bug introduced by this refactor,
    # so it is left as-is rather than "fixed".
    descent_start = descent_end = 0

    def close_descent():
        nonlocal descent_start, descent_end
        if descent_start and descent_end and descent_end - descent_start > 0:
            candidates.append([descent_start, descent_end, values[descent_start], values[descent_end]])
        descent_start = descent_end = 0

    for i, value in enumerate(values):
        if value > high or value < LOW:
            close_descent()
            continue
        if i == 0:
            continue
        previous = values[i - 1]
        if value > previous:
            close_descent()
        elif value == previous:
            if descent_start:
                descent_end = i
        elif descent_start:
            descent_end = i
        elif LOW < previous < high:
            descent_start, descent_end = i - 1, i
    close_descent()
    return candidates


def _is_accepted_event(candidate, values, drop, min_time, high):
    """A candidate counts as an event when it falls far/fast/long enough, and every
    sample across it stayed in range (no probe-out/out-of-range sample inside it)."""
    start, nadir, from_value, to_value = candidate
    duration, depth = nadir - start, from_value - to_value
    return bool(
        duration
        and depth >= drop
        and min_time <= duration <= MAX_TIME
        and depth // duration < MAX_AVERAGE
        and all(LOW <= values[k] <= high for k in range(start, nadir + 1))
    )


def _merge_and_accept(candidates, values, drop, min_time, high):
    """Fold a later candidate into the current one when it keeps falling further
    (allowing a small OSCILLATION rebound in between) and starts soon enough after the
    current nadir (within min_time) -- otherwise the current candidate is closed off
    and checked against `_is_accepted_event` before moving on to the next one."""
    accepted = []
    if not candidates:
        return accepted

    current = candidates[0][:]
    for candidate in candidates[1:]:
        current_start, current_nadir, current_from, current_to = current
        candidate_start, candidate_nadir, candidate_from, candidate_to = candidate
        joins_current = (
            candidate_from - current_to <= OSCILLATION
            and candidate_to < current_to
            and candidate_from < current_from
            and candidate_start - current_nadir <= min_time
        )
        if joins_current:
            current[1], current[3] = candidate_nadir, candidate_to
        else:
            if _is_accepted_event(current, values, drop, min_time, high):
                accepted.append(current)
            current = candidate[:]
    if _is_accepted_event(current, values, drop, min_time, high):
        accepted.append(current)

    return [dict(start=event[0], nadir=event[1], from_percent=event[2], to_percent=event[3]) for event in accepted]


def _valid_indices(series, low, high):
    """Indices of samples in [lo, hi]; None and out-of-range values (probe-out/artifact
    sentinels) are excluded, same rule `summarize`/`summarize_pulse` apply."""
    return [i for i, value in enumerate(series) if value is not None and low <= value <= high]


def _average_event_duration(events):
    """Mean event length in seconds (nadir - start), or None with no events."""
    return round(sum(event["nadir"] - event["start"] for event in events) / len(events), 1) if events else None


def _event_rate_stats(total_samples, valid_count, event_count):
    """The three report values shared by `summarize` and `summarize_pulse`:
    index_per_hour (events per hour of the whole recording), adjusted_index_per_hour
    (events per hour of valid data only, or None with no valid samples), and
    artifact_percent (share of samples that were invalid/probe-out)."""
    hours = total_samples / 3600.0
    return {
        "index_per_hour": round(event_count / hours, 2),
        "adjusted_index_per_hour": round(event_count / (valid_count / 3600.0), 2) if valid_count else None,
        "artifact_percent": round(100.0 * (total_samples - valid_count) / total_samples, 2),
    }


def summarize(spo2, events, criteria=CRITERIA):
    """Report values for a recording, named as in SpO2 Assistant's report."""
    valid = _valid_indices(spo2, 1, 100)
    out = dict(samples=len(spo2), valid_samples=len(valid), total_event=len(events))
    if not spo2:
        return out
    out.update(_event_rate_stats(len(spo2), len(valid), len(events)))
    out["average_low_spo2"] = round(sum(event["to_percent"] for event in events) / len(events), 2) if events else None
    low = [event for event in events if event["to_percent"] < criteria]
    out["events_below_criteria"] = len(low)
    out["average_low_spo2_below_criteria"] = round(sum(event["to_percent"] for event in low) / len(low), 2) if low else None
    # "Time (min) <criteria" (SPO2_FORMAT.md Sec7.1), same valid samples as the rest of
    # this report -- not a separately-filtered count (T-044).
    out["time_below_criteria_seconds"] = sum(1 for i in valid if spo2[i] < criteria)
    out["average_event_duration_seconds"] = _average_event_duration(events)
    inside = set()
    for event in events:
        inside.update(range(event["start"], event["nadir"] + 1))
    # SpO2.exe 0x54ced1-0x54d059: (sum of valid samples - sum over every event's
    # start..nadir) / (valid count - those samples); not computed when nothing is left.
    basal = [spo2[i] for i in valid if i not in inside]
    out["basal_spo2"] = round(sum(basal) / len(basal), 2) if basal else None
    return out


def summarize_pulse(pulse, events):
    """Pulse-channel report values (SPO2_FORMAT.md §7.1/§7.3; same formulas as `summarize`).
    Valid pulse is 1..250 like the rest of fiedle400, while the detector's own range is
    0..254; the program's artifact count may differ at the margins (T-035)."""
    valid_count = len(_valid_indices(pulse, 1, 250))
    out = dict(samples=len(pulse), valid_samples=valid_count, total_event=len(events))
    if not pulse:
        return out
    out.update(_event_rate_stats(len(pulse), valid_count, len(events)))
    out["average_event_duration_seconds"] = _average_event_duration(events)
    return out
