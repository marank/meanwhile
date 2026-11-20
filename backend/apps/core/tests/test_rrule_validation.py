"""
Repeat rules are checked when they come in, and series repeat at most hourly.
"""

from datetime import timedelta

import pytest

from apps.core.caldav.parsing import parse_series
from apps.core.models import Event
from apps.core.services.recurrence import expand_event
from apps.core.tests.helpers import BASE, Response, World, iso

pytestmark = pytest.mark.django_db


def _event(world: World, rrule: str) -> Response:
    return world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Series",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "rrule": rrule,
        },
    )


@pytest.mark.parametrize(
    "rrule", ["FREQ=BOGUS", "FREQ=SECONDLY", "FREQ=MINUTELY;COUNT=5", "INTERVAL=2", "FREQ=DAILY;UNTIL=soon"]
)
def test_unusable_rules_are_rejected(world: World, rrule: str) -> None:
    assert _event(world, rrule).status_code == 422


def test_usable_rules_are_kept(world: World) -> None:
    res = _event(world, "FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20300101")
    assert res.status_code == 200, res.content
    assert res.json()["rrule"] == "FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20300101"
    series = res.json()["id"]
    assert world["api"]["owner"].patch(f"/events/{series}", {"rrule": "FREQ=SECONDLY"}).status_code == 422


def test_caldav_rejects_unusable_rules() -> None:
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:x\r\n"
        "DTSTART:20300101T090000Z\r\nDTEND:20300101T100000Z\r\nRRULE:FREQ=SECONDLY\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    with pytest.raises(ValueError):
        parse_series(ics)


def test_rules_stored_earlier_count_as_single_events(world: World) -> None:
    res = _event(world, "FREQ=DAILY;COUNT=3")
    event = Event.objects.get(id=res.json()["id"])
    Event.objects.filter(id=event.id).update(rrule="FREQ=BOGUS")
    event.refresh_from_db()
    occurrences = expand_event(event, BASE - timedelta(days=1), BASE + timedelta(days=5))
    assert [start for start, _ in occurrences] == [event.start]
    # The calendar still loads, and so does its feed.
    res = world["api"]["owner"].get(
        f"/calendars/{world['cal']['id']}/events?start={iso(BASE - timedelta(days=1)).replace('+', '%2B')}"
        f"&end={iso(BASE + timedelta(days=5)).replace('+', '%2B')}"
    )
    assert res.status_code == 200, res.content


def test_dense_series_expand_only_up_to_the_limit(world: World) -> None:
    res = _event(world, "FREQ=HOURLY")
    event = Event.objects.get(id=res.json()["id"])
    # Stored before the check: one occurrence a second over ten years.
    Event.objects.filter(id=event.id).update(rrule="FREQ=SECONDLY")
    event.refresh_from_db()
    occurrences = expand_event(event, BASE, BASE + timedelta(days=3650), max_occurrences=50)
    assert len(occurrences) == 50
    assert occurrences[1][0] - occurrences[0][0] == timedelta(seconds=1)
