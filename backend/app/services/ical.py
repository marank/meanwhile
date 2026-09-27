from datetime import datetime, timedelta, timezone
from typing import List

import icalendar
from icalendar import Calendar as ICalCalendar
from icalendar import Event as ICalEvent

from app.models import Event, EventStatus


PRODID = "-//Calendar App//EN"


def _skip_status(status: str) -> bool:
    return status in {EventStatus.REJECTED.value, EventStatus.CANCELLED.value}


def _map_status(status: str) -> str:
    if status == EventStatus.PENDING.value:
        return "TENTATIVE"
    return "CONFIRMED"


def build_event_ical(event: Event) -> ICalEvent:
    # Reuse the stored component (e.g. imported via CalDAV) so unknown
    # properties survive, but always rewrite fields owned by the app.
    vevent = None
    if event.raw_ical:
        try:
            parsed = icalendar.Calendar.from_ical(event.raw_ical)
            for component in parsed.walk():
                if component.name == "VEVENT":
                    vevent = component
                    break
        except Exception:
            vevent = None

    if vevent is None:
        vevent = ICalEvent()
        vevent.add("uid", event.uid)
        vevent.add("created", event.created_at)

    for key in ("SUMMARY", "DESCRIPTION", "DTSTART", "DTEND", "DTSTAMP", "STATUS", "RRULE"):
        vevent.pop(key, None)

    vevent.add("summary", event.title)
    if event.description:
        vevent.add("description", event.description)
    if event.all_day:
        vevent.add("dtstart", event.start.date())
        # All-day multi-day
        vevent.add("dtend", event.end.date() + timedelta(days=1))
    else:
        vevent.add("dtstart", event.start)
        vevent.add("dtend", event.end)
    # Derived from updated_at so repeated serialization is stable (CalDAV ETags).
    vevent.add("dtstamp", event.updated_at or datetime.now(timezone.utc))
    vevent.add("status", _map_status(event.status))
    if event.rrule:
        vevent.add("rrule", event.rrule)
    return vevent


def _new_calendar() -> ICalCalendar:
    cal = ICalCalendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    return cal


def serialize_event_ical(event: Event) -> str:
    """Serialize a single event as a complete VCALENDAR object."""
    cal = _new_calendar()
    cal.add_component(build_event_ical(event))
    return cal.to_ical().decode("utf-8")


def event_ical_text(event: Event) -> str:
    """Stored iCalendar text for CalDAV, upgrading legacy bare VEVENT rows."""
    text = event.raw_ical
    if text and text.lstrip().startswith("BEGIN:VCALENDAR"):
        return text
    return serialize_event_ical(event)


def build_calendar_feed(events: List[Event]) -> str:
    cal = _new_calendar()
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    for event in events:
        if _skip_status(event.status):
            continue
        cal.add_component(build_event_ical(event))

    return cal.to_ical().decode("utf-8")
