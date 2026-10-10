"""
Recurrence expansion and conflict detection.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from core.models.events import Event


def make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def zone(name: str | None):
    """The zone for an IANA name; unknown names fall back to UTC."""
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _rule(event: Event, event_start: datetime):
    # Timed events repeat in their own zone, so weekdays and wall-clock times stay put across
    # midnight in UTC and daylight saving changes. All-day events are dates and repeat in UTC.
    dtstart = event_start if event.all_day else event_start.astimezone(zone(event.timezone))
    return rrulestr(event.rrule, dtstart=dtstart)


def expand_event(
    event: Event,
    range_start: datetime,
    range_end: datetime,
    max_occurrences: int = 1000,
):
    """Return (start, end) tuples for occurrences overlapping [range_start, range_end)."""
    event_start = make_aware(event.start)
    event_end = make_aware(event.end) + (
        timedelta(days=1) if event.all_day else timedelta()
    )
    duration = event_end - event_start
    if event.rrule is None:
        if event_start < range_end and event_end > range_start:
            return [(event_start, event_end)]
        return []

    rule = _rule(event, event_start)
    starts = rule.between(range_start - duration, range_end, inc=True)
    occurrences = []
    for start in starts[:max_occurrences]:
        occ_start = make_aware(start)
        occ_end = occ_start + duration
        if occ_end > range_start:
            occurrences.append((occ_start, occ_end))
    return occurrences


def recurrence_count(event: Event, occurrence_start: datetime) -> int:
    if event.rrule is None:
        return 0
    event_start = make_aware(event.start)
    rule = _rule(event, event_start)
    return max(
        0, len(rule.between(event_start, make_aware(occurrence_start), inc=True)) - 1
    )


def expand_events(events, range_start: datetime, range_end: datetime):
    result = []
    for event in events:
        for start, end in expand_event(event, range_start, range_end):
            result.append((event, start, end))
    return result


def find_conflicts(candidate: Event, existing_events, horizon_end: datetime):
    range_start = make_aware(candidate.start)
    range_end = make_aware(horizon_end)
    candidate_starts = expand_event(candidate, range_start, range_end)
    if not candidate_starts:
        return []

    conflicting = []
    for existing in existing_events:
        if str(existing.id) == str(candidate.id):
            continue
        existing_starts = expand_event(existing, range_start, range_end)
        if _series_overlap(candidate_starts, existing_starts):
            conflicting.append(existing)
    return conflicting


def _series_overlap(a, b) -> bool:
    for a_start, a_end in a:
        for b_start, b_end in b:
            if a_start < b_end and b_start < a_end:
                return True
    return False
