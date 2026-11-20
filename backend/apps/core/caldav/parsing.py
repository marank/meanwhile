"""
Reading events from the iCalendar objects CalDAV clients send.
"""

from datetime import UTC, date, datetime, timedelta, tzinfo
from functools import lru_cache
from typing import Any, TypedDict
from zoneinfo import ZoneInfo, available_timezones

import vobject
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.core.services.recurrence import iana_zone_name, validate_rrule, zone
from apps.core.services.reminders import allowed_minutes

# Longest title the database keeps; longer ones are cut.
TITLE_MAX_LENGTH = 255

# vobject ships no types: its components and properties are Any here.

PARTSTATS = {
    "NEEDS-ACTION": "needs_action",
    "ACCEPTED": "accepted",
    "DECLINED": "declined",
    "TENTATIVE": "tentative",
}


def to_utc(dt: datetime | date, naive_zone: tzinfo = UTC) -> datetime:
    """A date or date-time in UTC; date-times without a zone are taken to be in `naive_zone`."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=naive_zone)
        return dt.astimezone(UTC)
    return datetime(dt.year, dt.month, dt.day, tzinfo=UTC)


def _tzid(line: Any) -> str | None:
    # vobject moves the TZID parameter aside when it resolves the zone.
    params = line.params
    tzid: str | None = (params.get("X-VOBJ-ORIGINAL-TZID") or params.get("TZID") or [None])[0]
    return tzid


def _naive_zone(line: Any, floating: str) -> tzinfo:
    """The zone of a property's date-times that came without one: its TZID if known, else `floating`."""
    name = iana_zone_name(_tzid(line))
    return zone(name or floating)


def _times(vevent: Any, name: str, floating: str) -> set[datetime]:
    """All values of a date list property (EXDATE, RDATE) in UTC."""
    result: set[datetime] = set()
    for line in vevent.contents.get(name, []):
        values = line.value if isinstance(line.value, list) else [line.value]
        for value in values:
            if isinstance(value, tuple):
                # RDATE as a PERIOD: only its start is an occurrence.
                value = value[0]
            result.add(to_utc(value, _naive_zone(line, floating)))
    return result


def _email(address: object) -> str:
    text = str(address).strip()
    return (text[7:] if text.lower().startswith("mailto:") else text).lower()


def _attendee_email(address: object) -> str | None:
    """The email address of an ATTENDEE, or None for others (e.g. urn:uuid:..., or not an address)."""
    text = str(address).strip()
    if not text.lower().startswith("mailto:"):
        return None
    email = text[7:].lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email if len(email) <= 254 else None


def _zone_like(zone_info: tzinfo, around: datetime, preferred: str) -> str | None:
    """An IANA zone with the same offsets as a zone a client defined itself (a VTIMEZONE under a name
    like "Customized Time Zone"), around the event's start; the writer's own zone if it fits."""
    samples = tuple(around.replace(tzinfo=None) + timedelta(days=15 * k) for k in range(-4, 50))
    try:
        offsets = tuple(zone_info.utcoffset(sample) for sample in samples)
    except Exception:
        return None
    return _zone_with_offsets(offsets, samples, preferred)


@lru_cache(maxsize=256)
def _zone_with_offsets(
    offsets: tuple[timedelta | None, ...], samples: tuple[datetime, ...], preferred: str
) -> str | None:
    for name in [preferred, *sorted(available_timezones())]:
        zone_info = ZoneInfo(name)
        if all(zone_info.utcoffset(sample) == offset for sample, offset in zip(samples, offsets, strict=True)):
            return name
    return None


def _alarm_minutes(vevent: Any, start: datetime, end: datetime) -> list[int] | None:
    """Minutes before the start of each VALARM; None if the event carries no VALARM at all."""
    alarms = vevent.contents.get("valarm")
    if not alarms:
        return None
    minutes: set[int] = set()
    for alarm in alarms:
        if not hasattr(alarm, "trigger"):
            continue
        trigger = alarm.trigger.value
        if isinstance(trigger, timedelta):
            related = (alarm.trigger.params.get("RELATED") or ["START"])[0].upper()
            at = (end if related == "END" else start) + trigger
        else:
            at = to_utc(trigger)
        before = int((start - at).total_seconds() // 60)
        minutes.add(before)
    # Reminders after the start make no sense here; the rest within the app's bounds.
    return allowed_minutes(minutes)


class EventData(TypedDict):
    """The fields of one VEVENT (component_data)."""

    title: str
    description: str
    location: str
    start: datetime
    end: datetime
    all_day: bool
    timezone: str
    rrule: str | None
    uid: str | None
    recurrence_id: datetime | None
    exdates: set[datetime]
    rdates: set[datetime]
    categories: list[str]
    organizer: str | None
    # (email, status) of each participant.
    attendees: list[tuple[str, str]]
    alarms: list[int] | None


def component_data(vevent: Any, floating: str) -> EventData:
    """The fields of one VEVENT, with ends stored the way the app does (inclusive for all-day events).

    `floating`: the zone (IANA name) for times that come without one.
    """
    if not hasattr(vevent, "dtstart"):
        raise ValueError("VEVENT without DTSTART")
    dtstart = vevent.dtstart.value
    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
    if hasattr(vevent, "dtend"):
        dtend = vevent.dtend.value
    elif hasattr(vevent, "duration"):
        dtend = dtstart + vevent.duration.value
    else:
        # RFC 5545: without an end, an all-day event lasts its day and a timed event no time at all.
        dtend = dtstart + timedelta(days=1) if all_day else dtstart

    naive_zone = _naive_zone(vevent.dtstart, floating)
    start = to_utc(dtstart, naive_zone)
    end = to_utc(dtend, _naive_zone(vevent.dtend, floating) if hasattr(vevent, "dtend") else naive_zone)
    if end < start:
        raise ValueError("The event ends before it starts")
    if all_day:
        # iCalendar's DTEND is the day after an all-day event; the app stores its last day.
        end = max(start, end - timedelta(days=1))

    # The zone the client planned the event in, so its recurrences repeat in local time.
    event_timezone = "UTC"
    if not all_day:
        name = iana_zone_name(_tzid(vevent.dtstart) or getattr(dtstart.tzinfo, "zone", None))
        if name:
            event_timezone = name
        elif dtstart.tzinfo is None:
            event_timezone = floating
        else:
            # A zone the client defined itself: the IANA zone that keeps its local times, if any.
            event_timezone = _zone_like(dtstart.tzinfo, dtstart, floating) or "UTC"

    recurrence_id = None
    if hasattr(vevent, "recurrence_id"):
        recurrence_id = to_utc(vevent.recurrence_id.value, _naive_zone(vevent.recurrence_id, floating))

    categories: list[str] = []
    for line in vevent.contents.get("categories", []):
        values = line.value if isinstance(line.value, list) else [line.value]
        categories += [str(v).strip() for v in values if str(v).strip()]

    organizer = _email(vevent.organizer.value) if hasattr(vevent, "organizer") else None
    attendees: list[tuple[str, str]] = []
    for line in vevent.contents.get("attendee", []):
        email = _attendee_email(line.value)
        if email is None:
            continue  # rooms and groups by URN and the like; the app invites people by email
        partstat = (line.params.get("PARTSTAT") or ["NEEDS-ACTION"])[0].upper()
        attendees.append((email, PARTSTATS.get(partstat, "needs_action")))

    return {
        "title": str(vevent.summary.value)[:TITLE_MAX_LENGTH] if hasattr(vevent, "summary") else "",
        "description": str(vevent.description.value) if hasattr(vevent, "description") else "",
        "location": str(vevent.location.value)[:TITLE_MAX_LENGTH] if hasattr(vevent, "location") else "",
        "start": start,
        "end": end,
        "all_day": all_day,
        "timezone": event_timezone,
        "rrule": validate_rrule(str(vevent.rrule.value)) if hasattr(vevent, "rrule") else None,
        "uid": str(vevent.uid.value) if hasattr(vevent, "uid") else None,
        "recurrence_id": recurrence_id,
        "exdates": _times(vevent, "exdate", floating),
        "rdates": _times(vevent, "rdate", floating),
        "categories": categories,
        "organizer": organizer,
        "attendees": attendees,
        "alarms": _alarm_minutes(vevent, start, end),
    }


def parse_series(text: str, floating: str = "UTC") -> tuple[EventData, list[EventData]]:
    """The series (or single event) and its changed occurrences from one iCalendar object."""
    try:
        vcal = vobject.readOne(text)
        components = [component_data(v, floating) for v in vcal.contents.get("vevent", [])]
    except Exception as exc:
        raise ValueError("Failed to parse iCalendar object") from exc
    if not components:
        raise ValueError("Only events (VEVENT) can be stored in this calendar")
    series = next((c for c in components if c["recurrence_id"] is None), None)
    if series is None:
        # Only changed occurrences, e.g. an invitation to one meeting of a series: kept as a single event.
        series = components[0]
        series["recurrence_id"] = None
        return series, []
    is_series = bool(series["rrule"] or series["rdates"])
    overrides = [c for c in components if c["recurrence_id"] is not None] if is_series else []
    return series, overrides
