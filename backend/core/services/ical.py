"""
iCalendar serialization.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import icalendar
from django.conf import settings
from django.utils import timezone
from icalendar import Calendar as ICalCalendar
from icalendar import Event as ICalEvent

from core.models.base import EventStatus
from core.models.events import Event, EventParticipant
from core.models.users import User
from core.services.recurrence import as_utc, is_series, normalized_rrule, parse_exdates, zone

PRODID = "-//Meanwhile//EN"

# What others see of a calendar (feed, CalDAV): pending, rejected and cancelled bookings stay out.
SHARED_STATUSES = {EventStatus.CONFIRMED, EventStatus.APPROVED}
_GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}

# Properties written from the database; everything else a client stored is passed through.
_OWN_PROPERTIES = (
    "SUMMARY", "DESCRIPTION", "DTSTART", "DTEND", "DURATION", "DTSTAMP", "STATUS",
    "RRULE", "RDATE", "EXDATE", "RECURRENCE-ID", "UID",
    "CATEGORIES", "LOCATION", "RESOURCES", "ORGANIZER", "ATTENDEE", "SEQUENCE",
)

PARTSTAT = {
    "needs_action": "NEEDS-ACTION",
    "accepted": "ACCEPTED",
    "declined": "DECLINED",
    "tentative": "TENTATIVE",
}


@dataclass
class Audience:
    """Who an iCalendar object is written for.

    `viewer`: the CalDAV user, whose reminders become VALARMs; None for the public feed.
    `people`: whether organizer and participants are included (not in the public feed).
    `scheduling`: written for an iMIP message to participants: the organizer is the address
    that receives their answers, and they're asked to answer.
    """

    viewer: User | None = None
    people: bool = False
    scheduling: bool = False


CALDAV = Audience(people=True)
FEED = Audience()
SCHEDULING = Audience(people=True, scheduling=True)


def caldav_audience(viewer: User | None) -> Audience:
    return Audience(viewer=viewer, people=True)


def _map_status(status: str) -> str:
    if status == EventStatus.PENDING:
        return "TENTATIVE"
    return "CONFIRMED"


def _raw_components(event: Event) -> dict:
    """The VEVENTs a client stored with the series, by recurrence id (None for the series itself)."""
    components = {}
    if not event.raw_ical:
        return components
    try:
        parsed = icalendar.Calendar.from_ical(event.raw_ical)
    except Exception:
        return components
    for component in parsed.walk("VEVENT"):
        rid = component.get("RECURRENCE-ID")
        key = None
        if rid is not None:
            value = rid.dt
            key = as_utc(value if isinstance(value, datetime) else datetime(value.year, value.month, value.day))
        components.setdefault(key, component)
    return components


def _ical_time(event: Event, value: datetime):
    """A start as written in iCalendar: a date for all-day events, local time with TZID otherwise."""
    if event.all_day:
        return as_utc(value).date()
    return value.astimezone(zone(event.timezone))


def _raw_texts(raw: ICalEvent | None, name: str) -> list[str]:
    """The text values of a property a client stored, e.g. every CATEGORIES value."""
    if raw is None or name not in raw:
        return []
    values = raw.get(name)
    values = values if isinstance(values, list) else [values]
    texts = []
    for value in values:
        cats = getattr(value, "cats", None)
        if cats is not None:
            texts.extend(str(c) for c in cats)
        else:
            texts.append(str(value))
    return [t for t in texts if t]


def _participants(event: Event) -> list[EventParticipant]:
    return list(event.participants.all())


def _reminder_minutes(event: Event, viewer: User) -> list[int]:
    reminders = getattr(event, "viewer_reminders", None)
    if reminders is None:
        reminders = event.reminders.filter(user=viewer)
    return sorted({r.minutes_before for r in reminders})


def _add_alarms(vevent: ICalEvent, minutes: list[int]) -> None:
    for before in minutes:
        alarm = icalendar.Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", vevent.get("SUMMARY") or "Reminder")
        alarm.add("trigger", -timedelta(minutes=before))
        vevent.add_component(alarm)


def organizer_address(organizer: User, scheduling: bool) -> str:
    """Where participants' answers go: to the app's iMIP mailbox if there is one."""
    if scheduling and settings.IMIP_ADDRESS:
        return settings.IMIP_ADDRESS
    return organizer.email


def _add_people(vevent: ICalEvent, event: Event, organizer: User | None, scheduling: bool = False) -> None:
    participants = _participants(event)
    if not participants:
        return
    if organizer is not None:
        vevent.add(
            "organizer",
            icalendar.vCalAddress(f"mailto:{organizer_address(organizer, scheduling)}"),
            parameters={"CN": organizer.display_name or organizer.email},
        )
    for participant in participants:
        params = {"PARTSTAT": PARTSTAT.get(participant.status, "NEEDS-ACTION"), "ROLE": "REQ-PARTICIPANT"}
        if participant.user is not None and participant.user.display_name:
            params["CN"] = participant.user.display_name
        if scheduling:
            params["RSVP"] = "TRUE"
        vevent.add("attendee", icalendar.vCalAddress(f"mailto:{participant.email}"), parameters=params)


def _raw_sequence(raw: ICalEvent | None) -> int:
    try:
        return int(raw.get("SEQUENCE", 0)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def build_event_ical(
    event: Event,
    raw: ICalEvent | None = None,
    exdates=(),
    uid: str | None = None,
    audience: Audience = FEED,
    category_names: set[str] = frozenset(),
    organizer: User | None = None,
) -> ICalEvent:
    """One VEVENT; `category_names` are the lowercase names of its calendar's categories."""
    vevent = ICalEvent()
    if raw is not None:
        for name, value in raw.property_items(recursive=False):
            if name not in ("BEGIN", "END") and name not in _OWN_PROPERTIES:
                vevent.add(name, value, encode=False)
        for sub in raw.subcomponents:
            # Reminders are kept per user and written below.
            if sub.name != "VALARM":
                vevent.add_component(sub)
    if "CREATED" not in vevent:
        vevent.add("created", event.created_at)

    vevent.add("uid", uid or event.uid)
    vevent.add("summary", event.title)
    if event.description:
        vevent.add("description", event.description)
    if event.all_day:
        # Stored ends are inclusive; iCalendar's DTEND is the day after.
        vevent.add("dtstart", as_utc(event.start).date())
        vevent.add("dtend", as_utc(event.end).date() + timedelta(days=1))
    else:
        # Local times with TZID, so clients repeat the series in the zone it was planned in.
        vevent.add("dtstart", _ical_time(event, event.start))
        vevent.add("dtend", _ical_time(event, event.end))
    if event.recurrence_id is not None:
        series = event.parent
        vevent.add("recurrence-id", _ical_time(series, event.recurrence_id))
    vevent.add("dtstamp", event.updated_at or timezone.now())
    # Changes sent to participants count up; a client's own count is kept if it is higher.
    sequence = max((event.parent if event.parent_id else event).sequence, _raw_sequence(raw))
    if sequence or (raw is not None and "SEQUENCE" in raw):
        vevent.add("sequence", sequence)
    vevent.add("status", _map_status(event.status))
    if event.rrule:
        try:
            vevent.add("rrule", icalendar.vRecur.from_ical(normalized_rrule(event)))
        except ValueError:
            pass  # stored before rules were validated; the app shows the series as its first occurrence too
    if is_series(event):
        for start in sorted(parse_exdates(event.rdates)):
            vevent.add("rdate", _ical_time(event, start))
        for start in sorted(exdates):
            vevent.add("exdate", _ical_time(event, start))

    # The category first, then those of the client that aren't categories of the calendar.
    categories = [event.category.name] if event.category else []
    categories += [c for c in _raw_texts(raw, "CATEGORIES") if c.lower() not in category_names]
    if categories:
        vevent.add("categories", categories)
    # Strictly apart: where the event takes place (a booked place is named there), and what
    # else it books.
    if event.location:
        vevent.add("location", event.location)
    if event.resource:
        vevent.add("resources", [event.resource.name])

    if audience.people:
        _add_people(vevent, event, organizer, audience.scheduling)
    if audience.viewer is not None:
        _add_alarms(vevent, _reminder_minutes(event.parent if event.parent_id else event, audience.viewer))
    return vevent


def _category_names(calendar) -> set[str]:
    cached = getattr(calendar, "_ical_category_names", None)
    if cached is None:
        cached = {name.lower() for name in calendar.categories.values_list("name", flat=True)}
        calendar._ical_category_names = cached
    return cached


def build_series_ical(event: Event, shared_only: bool = True, audience: Audience = FEED) -> list[ICalEvent]:
    """The series and its changed occurrences as VEVENTs sharing one UID.

    With `shared_only`, changed occurrences others may not see are written as removed.
    """
    raw = _raw_components(event)
    names = _category_names(event.calendar)
    organizer = event.creator if audience.people else None
    overrides = list(event.overrides.all()) if is_series(event) else []
    if audience.scheduling:
        # Participants see pending bookings too; rejected and cancelled ones are removed.
        visible = [o for o in overrides if o.status not in _GONE]
    else:
        visible = [o for o in overrides if not shared_only or o.status in SHARED_STATUSES]
    exdates = parse_exdates(event.exdates)
    exdates.update(as_utc(o.recurrence_id) for o in overrides if o not in visible)
    components = [
        build_event_ical(event, raw.get(None), exdates, audience=audience, category_names=names, organizer=organizer)
    ]
    for override in sorted(visible, key=lambda o: o.recurrence_id):
        override.parent = event
        components.append(
            build_event_ical(
                override,
                raw.get(override.recurrence_id),
                uid=event.uid,
                audience=audience,
                category_names=names,
                organizer=organizer,
            )
        )
    return components


def new_calendar(method: str | None = None) -> ICalCalendar:
    cal = ICalCalendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    if method:
        cal.add("method", method)
    return cal


def to_ical(cal: ICalCalendar) -> str:
    # Adds the VTIMEZONE definitions for every TZID used, as RFC 5545 requires.
    cal.add_missing_timezones()
    return cal.to_ical().decode("utf-8")


def serialize_event_ical(event: Event, audience: Audience = CALDAV) -> str:
    """The series of `event` (or the event itself) as one iCalendar object, as CalDAV serves it."""
    series = event.parent if event.parent_id else event
    cal = new_calendar()
    for component in build_series_ical(series, audience=audience):
        cal.add_component(component)
    return to_ical(cal)


def event_ical_text(event: Event, viewer: User | None = None) -> str:
    return serialize_event_ical(event, caldav_audience(viewer))


# How often subscribers should fetch the feed again.
FEED_REFRESH_INTERVAL = timedelta(hours=1)


def build_calendar_feed(calendar, events) -> str:
    """`events`: the series and single events of `calendar` that others may see."""
    cal = new_calendar()
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    # The name subscribers see instead of the feed URL: RFC 7986, and the X-WR form most clients read.
    cal.add("name", calendar.name)
    cal.add("x-wr-calname", calendar.name)
    if calendar.description:
        cal.add("description", calendar.description)
        cal.add("x-wr-caldesc", calendar.description)
    cal.add("x-apple-calendar-color", calendar.event_color)
    cal.add("refresh-interval", icalendar.vDuration(FEED_REFRESH_INTERVAL), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", icalendar.vDuration(FEED_REFRESH_INTERVAL))

    for event in events:
        if event.parent_id or event.status not in SHARED_STATUSES:
            continue
        event.calendar = calendar  # one object for all events, so that its categories are looked up once
        for component in build_series_ical(event):
            cal.add_component(component)

    return to_ical(cal)
