from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from dateutil.rrule import rrulestr

from app.models import Event


def _make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def expand_event(
    event: Event,
    range_start: datetime,
    range_end: datetime,
    max_occurrences: int = 1000,
) -> List[Tuple[datetime, datetime]]:
    """Return (start, end) tuples for all occurrences of *event* inside [range_start, range_end)."""
    event_start = _make_aware(event.start)
    event_end = _make_aware(event.end) + (timedelta(days=1) if event.all_day else timedelta())
    duration = event_end - event_start
    if event.rrule is None:
        if event_start < range_end and event_end > range_start:
            return [(event_start, event_end)]
        return []

    rule = rrulestr(event.rrule, dtstart=event_start)
    starts = rule.between(range_start, range_end, inc=True)
    return [(_make_aware(start), _make_aware(start) + duration) for start in starts[:max_occurrences]]


def recurrence_count(event: Event, occurrence_start: datetime) -> int:
    if event.rrule is None:
        return 0
    event_start = _make_aware(event.start)
    rule = rrulestr(event.rrule, dtstart=event_start)
    return max(0, len(rule.between(event_start, _make_aware(occurrence_start), inc=True)) - 1)


def expand_events(
    events: List[Event],
    range_start: datetime,
    range_end: datetime,
) -> List[Tuple[Event, datetime, datetime]]:
    result = []
    for event in events:
        for start, end in expand_event(event, range_start, range_end):
            result.append((event, start, end))
    return result


def find_conflicts(
    candidate: Event,
    existing_events: List[Event],
    horizon_end: datetime,
) -> List[Event]:
    """Return approved events that overlap *candidate* (or its recurrence series)."""
    range_start = _make_aware(candidate.start)
    range_end = _make_aware(horizon_end)
    candidate_starts = expand_event(
        candidate,
        range_start,
        range_end,
    )
    if not candidate_starts:
        return []

    conflicting = []
    for existing in existing_events:
        if existing.id == candidate.id:
            continue
        existing_starts = expand_event(existing, candidate.start, horizon_end)
        if _series_overlap(candidate_starts, existing_starts):
            conflicting.append(existing)
    return conflicting


def _series_overlap(
    a: List[Tuple[datetime, datetime]],
    b: List[Tuple[datetime, datetime]],
) -> bool:
    for a_start, a_end in a:
        for b_start, b_end in b:
            if a_start < b_end and b_start < a_end:
                return True
    return False
