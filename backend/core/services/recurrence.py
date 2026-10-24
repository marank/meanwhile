"""
Recurrence expansion and conflict detection.
"""

from datetime import UTC, date, datetime, time, timedelta
from itertools import islice, takewhile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rruleset, rrulestr
from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON

from core.models.events import Event


def as_utc(dt: datetime) -> datetime:
    """The date-time in UTC; one without a zone is taken to be in UTC already."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def zone(name: str | None):
    """The zone for an IANA name; unknown names fall back to UTC."""
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


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


# Finer rules would make every expansion of the series run through millions of occurrences.
ALLOWED_FREQUENCIES = {"YEARLY", "MONTHLY", "WEEKLY", "DAILY", "HOURLY"}


def validate_rrule(rule: str) -> str:
    """The RRULE value if dateutil can expand it and it repeats at most hourly; raises ValueError otherwise."""
    parts = rrule_parts(rule)
    if parts.get("FREQ", "").upper() not in ALLOWED_FREQUENCIES:
        raise ValueError(f"Unsupported repeat frequency {parts.get('FREQ')!r}")
    # UNTIL is checked by itself: dateutil only takes the type that matches DTSTART (normalized_rrule).
    until = parts.pop("UNTIL", None)
    if until is not None:
        _parse_until(until)
    rrulestr(format_rrule(parts), dtstart=datetime(2000, 1, 1))
    return rule


def _parse_until(value: str) -> date | datetime:
    """An UNTIL value: a date, a UTC date-time ("...Z") or a floating date-time."""
    if "T" not in value:
        return datetime.strptime(value[:8], "%Y%m%d").date()
    parsed = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=UTC) if value.endswith("Z") else parsed


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
            until = (until.astimezone(UTC) if until.tzinfo else until).date()
        parts["UNTIL"] = until.strftime("%Y%m%d")
    else:
        event_zone = zone(event.timezone)
        if not isinstance(until, datetime):
            # A date means "through that day" in the zone the series repeats in.
            until = datetime.combine(until, time(23, 59, 59), tzinfo=event_zone)
        elif until.tzinfo is None:
            until = until.replace(tzinfo=event_zone)
        parts["UNTIL"] = until.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return format_rrule(parts)


class _UtcRule:
    """All-day series repeat on floating dates; their occurrences are reported as UTC midnights."""

    def __init__(self, rule):
        self._rule = rule

    def between(self, after: datetime, before: datetime, inc: bool = False):
        naive = self._rule.between(
            after.astimezone(UTC).replace(tzinfo=None),
            before.astimezone(UTC).replace(tzinfo=None),
            inc=inc,
        )
        return [dt.replace(tzinfo=UTC) for dt in naive]

    def __iter__(self):
        return (dt.replace(tzinfo=UTC) for dt in self._rule)

    def xafter(self, after: datetime, inc: bool = False):
        naive = self._rule.xafter(after.astimezone(UTC).replace(tzinfo=None), inc=inc)
        return (dt.replace(tzinfo=UTC) for dt in naive)


def _rule(event: Event, event_start: datetime):
    # Timed events repeat in their own zone, so weekdays and wall-clock times stay put across
    # midnight in UTC and daylight saving changes. All-day events are dates and repeat in UTC.
    if event.all_day:
        def local(dt: datetime) -> datetime:
            return dt.astimezone(UTC).replace(tzinfo=None)
    else:
        event_zone = zone(event.timezone)

        def local(dt: datetime) -> datetime:
            return dt.astimezone(event_zone)

    rule = rruleset()
    rrule = normalized_rrule(event)
    try:
        if rrule:
            rule.rrule(rrulestr(rrule, dtstart=local(event_start)))
    except ValueError:
        # Stored before rules were validated (validate_rrule): the series is its first occurrence.
        rrule = None
    if not rrule:
        # Without a rule, the series is its first occurrence and the extra dates.
        rule.rdate(local(event_start))
    for extra in parse_exdates(event.rdates):
        rule.rdate(local(extra))
    return _UtcRule(rule) if event.all_day else rule


def parse_exdates(values) -> set[datetime]:
    result = set()
    for value in values or []:
        try:
            result.add(as_utc(datetime.fromisoformat(value)))
        except (TypeError, ValueError):
            continue
    return result


def format_exdate(dt: datetime) -> str:
    return as_utc(dt).isoformat()


def exception_starts(event: Event) -> set[datetime]:
    """Original starts of the occurrences that are removed from the series or replaced by overrides."""
    starts = parse_exdates(event.exdates)
    if event.pk:
        starts.update(
            rid
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
    event_start = as_utc(event.start)
    event_end = as_utc(event.end) + (
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
    # Lazily, so that only up to max_occurrences of a dense series are worked out.
    starts = takewhile(lambda start: start <= range_end, rule.xafter(range_start - duration, inc=True))
    occurrences = []
    for start in islice(starts, max_occurrences):
        occ_start = as_utc(start)
        occ_end = occ_start + duration
        if occ_end > range_start and occ_start not in exclude:
            occurrences.append((occ_start, occ_end))
    return occurrences


def occurrence_index(event: Event, start: datetime) -> int | None:
    """Position of the occurrence starting at `start` in the series (0 is the first), or None
    if the series has no occurrence then. Removed and overridden occurrences count."""
    if not is_series(event):
        return 0 if event.start == start else None
    starts = _rule(event, event.start).between(event.start, start, inc=True)
    if not starts or starts[-1] != start:
        return None
    return len(starts) - 1


def occurrence_starts(event: Event, after: datetime, exclude: set[datetime] | None = None):
    """The starts of the event's occurrences after `after`, in order (endless for an endless series).

    Like expand_event, without the removed and replaced ones; `exclude` passes their starts in.
    """
    if not is_series(event):
        if event.start > after:
            yield event.start
        return
    if exclude is None:
        exclude = exception_starts(event)
    for start in _rule(event, event.start).xafter(after):
        start = as_utc(start)
        if start not in exclude:
            yield start


def nth_occurrence(event: Event, index: int) -> datetime | None:
    if not is_series(event):
        return as_utc(event.start) if index == 0 else None
    found = next(islice(iter(_rule(event, event.start)), index, None), None)
    return as_utc(found) if found is not None else None


def recurrence_count(event: Event, occurrence_start: datetime) -> int:
    if not is_series(event):
        return 0
    rule = _rule(event, event.start)
    return max(0, len(rule.between(event.start, occurrence_start, inc=True)) - 1)


def expand_events(events, range_start: datetime, range_end: datetime):
    events = list(events)
    # One query for the overridden occurrences of every series instead of one per series.
    series_ids = [e.pk for e in events if is_series(e)]
    overridden: dict[str, set[datetime]] = {}
    for parent_id, rid in Event.objects.filter(parent_id__in=series_ids).values_list("parent_id", "recurrence_id"):
        if rid is not None:
            overridden.setdefault(parent_id, set()).add(rid)
    result = []
    for event in events:
        exclude = parse_exdates(event.exdates) | overridden.get(event.pk, set()) if is_series(event) else set()
        for start, end in expand_event(event, range_start, range_end, exclude=exclude):
            result.append((event, start, end))
    return result


def find_conflicts(candidate: Event, existing_events, horizon_end: datetime):
    range_start, range_end = candidate.start, horizon_end
    candidate_starts = expand_event(candidate, range_start, range_end)
    if not candidate_starts:
        return []

    conflicting = []
    for existing in existing_events:
        if existing.id == candidate.id:
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
