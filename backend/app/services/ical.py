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
    if event.raw_ical:
        try:
            component = icalendar.Calendar.from_ical(event.raw_ical)
            for component in component.walk():
                if component.name == "VEVENT":
                    return component
        except Exception:
            pass

    vevent = ICalEvent()
    vevent.add("uid", event.uid)
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
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("created", event.created_at)
    vevent.add("status", _map_status(event.status))
    if event.rrule:
        vevent.add("rrule", event.rrule)
    return vevent


def build_calendar_feed(events: List[Event]) -> str:
    cal = ICalCalendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    for event in events:
        if _skip_status(event.status):
            continue
        cal.add_component(build_event_ical(event))

    return cal.to_ical().decode("utf-8")
