"""
Recurrence expansion and conflict detection.
"""

from datetime import date, datetime, time, timedelta, timezone
from itertools import islice
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rruleset, rrulestr
from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON

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


def iana_zone_name(tzid: str | None) -> str | None:
    """The IANA name for a TZID from a client, or None if it names no known zone.

    Besides IANA names, Outlook sends Windows names ("W. Europe Standard Time") and old
    Thunderbird versions prefixed ones ("/mozilla.org/20070129_1/Europe/Berlin").
    """
    if not tzid:
        return None
    parts = tzid.strip("/").split("/")
    candidates = [tzid, WINDOWS_TO_OLSON.get(tzid)] + ["/".join(parts[i:]) for i in range(1, len(parts))]
    for candidate in candidates:
        if candidate and isinstance(zone(candidate), ZoneInfo):
            return candidate
    return None


def is_series(event: Event) -> bool:
    """Whether the event repeats: by a rule, by extra dates (RDATE), or both."""
    return bool(event.rrule or event.rdates)


def rrule_parts(rule: str) -> dict[str, str]:
    """The parts of an RRULE value ("FREQ=WEEKLY;COUNT=3") by name, in their order."""
    parts = {}
    for part in rule.strip().removeprefix("RRULE:").split(";"):
        name, _, value = part.partition("=")
        if name:
            parts[name.strip().upper()] = value.strip()
    return parts


def format_rrule(parts: dict[str, str]) -> str:
    return ";".join(f"{name}={value}" for name, value in parts.items())


def _parse_until(value: str) -> date | datetime:
    """An UNTIL value: a date, a UTC date-time ("...Z") or a floating date-time."""
    if "T" not in value:
        return datetime.strptime(value[:8], "%Y%m%d").date()
    parsed = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=timezone.utc) if value.endswith("Z") else parsed


def normalized_rrule(event: Event) -> str | None:
    """The event's rule with UNTIL of the type RFC 5545 asks for: a date for all-day events,
    a UTC date-time otherwise. Clients send either, and dateutil rejects a mismatch."""
    if not event.rrule:
        return None
    parts = rrule_parts(event.rrule)
    if "UNTIL" not in parts:
        return format_rrule(parts)
    try:
        until = _parse_until(parts["UNTIL"])
    except ValueError:
        parts.pop("UNTIL")
        return format_rrule(parts)
    if event.all_day:
        if isinstance(until, datetime):
            until = (until.astimezone(timezone.utc) if until.tzinfo else until).date()
        parts["UNTIL"] = until.strftime("%Y%m%d")
    else:
        event_zone = zone(event.timezone)
        if not isinstance(until, datetime):
            # A date means "through that day" in the zone the series repeats in.
            until = datetime.combine(until, time(23, 59, 59), tzinfo=event_zone)
        elif until.tzinfo is None:
            until = until.replace(tzinfo=event_zone)
        parts["UNTIL"] = until.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return format_rrule(parts)


class _UtcRule:
    """All-day series repeat on floating dates; their occurrences are reported as UTC midnights."""

    def __init__(self, rule):
        self._rule = rule

    def between(self, after: datetime, before: datetime, inc: bool = False):
        naive = self._rule.between(
            after.astimezone(timezone.utc).replace(tzinfo=None),
            before.astimezone(timezone.utc).replace(tzinfo=None),
            inc=inc,
        )
        return [dt.replace(tzinfo=timezone.utc) for dt in naive]

    def __iter__(self):
        return (dt.replace(tzinfo=timezone.utc) for dt in self._rule)


def _rule(event: Event, event_start: datetime):
    # Timed events repeat in their own zone, so weekdays and wall-clock times stay put across
    # midnight in UTC and daylight saving changes. All-day events are dates and repeat in UTC.
    if event.all_day:
        def local(dt: datetime) -> datetime:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        event_zone = zone(event.timezone)

        def local(dt: datetime) -> datetime:
            return dt.astimezone(event_zone)

    rule = rruleset()
    rrule = normalized_rrule(event)
    if rrule:
        rule.rrule(rrulestr(rrule, dtstart=local(event_start)))
    else:
        # Without a rule, the series is its first occurrence and the extra dates.
        rule.rdate(local(event_start))
    for extra in parse_exdates(event.rdates):
        rule.rdate(local(extra))
    return _UtcRule(rule) if event.all_day else rule


def parse_exdates(values) -> set[datetime]:
    result = set()
    for value in values or []:
        try:
            result.add(make_aware(datetime.fromisoformat(value)))
        except (TypeError, ValueError):
            continue
    return result


def format_exdate(dt: datetime) -> str:
    return make_aware(dt).isoformat()


def exception_starts(event: Event) -> set[datetime]:
    """Original starts of the occurrences that are removed from the series or replaced by overrides."""
    starts = parse_exdates(event.exdates)
    if event.pk:
        starts.update(
            make_aware(rid)
            for rid in Event.objects.filter(parent_id=event.pk).values_list("recurrence_id", flat=True)
            if rid is not None
        )
    return starts


def expand_event(
    event: Event,
    range_start: datetime,
    range_end: datetime,
    max_occurrences: int = 1000,
    exclude: set[datetime] | None = None,
):
    """Return (start, end) tuples for occurrences overlapping [range_start, range_end).

    Occurrences that were removed or replaced by an override are left out; `exclude` passes
    their starts in when they are already known.
    """
    event_start = make_aware(event.start)
    event_end = make_aware(event.end) + (
        timedelta(days=1) if event.all_day else timedelta()
    )
    duration = event_end - event_start
    if not is_series(event):
        if event_start < range_end and event_end > range_start:
            return [(event_start, event_end)]
        return []

    if exclude is None:
        exclude = exception_starts(event)
    rule = _rule(event, event_start)
    starts = rule.between(range_start - duration, range_end, inc=True)
    occurrences = []
    for start in starts[:max_occurrences]:
        occ_start = make_aware(start)
        occ_end = occ_start + duration
        if occ_end > range_start and occ_start not in exclude:
            occurrences.append((occ_start, occ_end))
    return occurrences


def occurrence_index(event: Event, start: datetime) -> int | None:
    """Position of the occurrence starting at `start` in the series (0 is the first), or None
    if the series has no occurrence then. Removed and overridden occurrences count."""
    if not is_series(event):
        return 0 if make_aware(event.start) == make_aware(start) else None
    event_start = make_aware(event.start)
    start = make_aware(start)
    starts = _rule(event, event_start).between(event_start, start, inc=True)
    if not starts or make_aware(starts[-1]) != start:
        return None
    return len(starts) - 1


def nth_occurrence(event: Event, index: int) -> datetime | None:
    if not is_series(event):
        return make_aware(event.start) if index == 0 else None
    found = next(islice(iter(_rule(event, make_aware(event.start))), index, None), None)
    return make_aware(found) if found is not None else None


def recurrence_count(event: Event, occurrence_start: datetime) -> int:
    if not is_series(event):
        return 0
    event_start = make_aware(event.start)
    rule = _rule(event, event_start)
    return max(
        0, len(rule.between(event_start, make_aware(occurrence_start), inc=True)) - 1
    )


def expand_events(events, range_start: datetime, range_end: datetime):
    events = list(events)
    # One query for the overridden occurrences of every series instead of one per series.
    series_ids = [e.pk for e in events if is_series(e)]
    overridden: dict[str, set[datetime]] = {}
    for parent_id, rid in Event.objects.filter(parent_id__in=series_ids).values_list("parent_id", "recurrence_id"):
        if rid is not None:
            overridden.setdefault(parent_id, set()).add(make_aware(rid))
    result = []
    for event in events:
        exclude = parse_exdates(event.exdates) | overridden.get(event.pk, set()) if is_series(event) else set()
        for start, end in expand_event(event, range_start, range_end, exclude=exclude):
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
