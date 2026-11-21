"""
What update emails show of a change, and the ends of events CalDAV clients send without one.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core import mail as django_mail
from django.core.mail import EmailMultiAlternatives

from apps.core.caldav.parsing import parse_series
from apps.core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db

GUEST = "guest@elsewhere.test"


def test_updates_show_a_taken_out_place_and_the_old_title_and_description(world: World) -> None:
    api = world["api"]["owner"]
    res = api.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Planning",
            "description": "Agenda",
            "location": "Room 1",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "timezone": "Europe/Berlin",
        },
    )
    event: dict[str, Any] = res.json()
    api.post(f"/events/{event['id']}/participants", {"email": GUEST})
    django_mail.outbox.clear()

    api.patch(f"/events/{event['id']}", {"title": "Retro", "description": "", "location": ""})

    [update] = [m for m in django_mail.outbox if m.to == [GUEST]]
    # The place stays as an empty row, and so does the description, each with what it said before.
    assert "Where: —" in update.body
    assert "Description: —" in update.body
    assert isinstance(update, EmailMultiAlternatives)
    html = str(next(content for content, mimetype in update.alternatives if mimetype == "text/html"))
    before = re.findall(r'<div class="mw-before"[^>]*>([^<]*)</div>', html)
    assert {"Planning", "Room 1", "Agenda"} <= set(before)


def vevent(*lines: str) -> str:
    """An iCalendar object with one VEVENT of the given lines."""
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VEVENT",
            "UID:x",
            "DTSTAMP:20300101T000000Z",
            "SUMMARY:Planning",
            *lines,
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


@pytest.mark.parametrize(
    ("lines", "start", "end"),
    [
        # RFC 5545: without an end, an all-day event lasts its day (stored with its last day)...
        (["DTSTART;VALUE=DATE:20300107"], datetime(2030, 1, 7, tzinfo=UTC), datetime(2030, 1, 7, tzinfo=UTC)),
        # ...and a timed event no time at all.
        (["DTSTART:20300107T090000Z"], datetime(2030, 1, 7, 9, tzinfo=UTC), datetime(2030, 1, 7, 9, tzinfo=UTC)),
        (
            ["DTSTART:20300107T090000Z", "DURATION:PT90M"],
            datetime(2030, 1, 7, 9, tzinfo=UTC),
            datetime(2030, 1, 7, 10, 30, tzinfo=UTC),
        ),
    ],
)
def test_events_without_dtend_end_by_duration_or_by_default(lines: list[str], start: datetime, end: datetime) -> None:
    series, _ = parse_series(vevent(*lines))
    assert (series["start"], series["end"]) == (start, end)


def test_events_without_dtstart_are_refused() -> None:
    with pytest.raises(ValueError, match="Failed to parse"):
        parse_series(vevent("DTEND:20300107T090000Z"))
