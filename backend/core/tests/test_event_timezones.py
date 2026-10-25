"""
Recurring events repeat in the zone they were planned in, not in UTC.
"""

from typing import Any

import pytest

from core.models import Event
from core.services.ical import serialize_event_ical
from core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db

BERLIN = "Europe/Berlin"


@pytest.fixture
def owner() -> Api:
    return Api(make_user("owner"))


@pytest.fixture
def calendar(owner: Api) -> dict[str, Any]:
    calendar: dict[str, Any] = owner.post("/calendars", {"name": "Team"}).json()
    return calendar


def create(owner: Api, calendar: dict[str, Any], **fields: Any) -> dict[str, Any]:
    res = owner.post(f"/calendars/{calendar['id']}/events", {"title": "Series", **fields})
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def occurrence_starts(owner: Api, calendar: dict[str, Any], start: str, end: str) -> list[str]:
    res = owner.get(f"/calendars/{calendar['id']}/events?start={start}&end={end}")
    assert res.status_code == 200, res.content
    return [o["start"].replace("+00:00", "Z") for o in res.json()]


def test_weekday_rules_use_the_local_weekday(owner: Api, calendar: dict[str, Any]) -> None:
    # Wednesday 00:30 in Berlin is still Tuesday in UTC.
    create(
        owner,
        calendar,
        start="2026-10-06T22:30:00Z",
        end="2026-10-06T23:30:00Z",
        rrule="FREQ=WEEKLY;BYDAY=WE",
        timezone=BERLIN,
    )
    starts = occurrence_starts(owner, calendar, "2026-10-01T00:00:00Z", "2026-10-22T00:00:00Z")
    assert starts == ["2026-10-06T22:30:00Z", "2026-10-13T22:30:00Z", "2026-10-20T22:30:00Z"]


def test_local_time_survives_daylight_saving_changes(owner: Api, calendar: dict[str, Any]) -> None:
    # 09:00 in Berlin: 07:00 UTC in summer time, 08:00 UTC after the change on 25 October.
    create(
        owner, calendar, start="2026-10-19T07:00:00Z", end="2026-10-19T08:00:00Z", rrule="FREQ=WEEKLY", timezone=BERLIN
    )
    starts = occurrence_starts(owner, calendar, "2026-10-18T00:00:00Z", "2026-10-28T00:00:00Z")
    assert starts == ["2026-10-19T07:00:00Z", "2026-10-26T08:00:00Z"]


def test_events_without_a_zone_repeat_in_utc(owner: Api, calendar: dict[str, Any]) -> None:
    event = create(owner, calendar, start="2026-10-19T07:00:00Z", end="2026-10-19T08:00:00Z", rrule="FREQ=WEEKLY")
    assert event["timezone"] == "UTC"
    starts = occurrence_starts(owner, calendar, "2026-10-18T00:00:00Z", "2026-10-28T00:00:00Z")
    assert starts == ["2026-10-19T07:00:00Z", "2026-10-26T07:00:00Z"]


def test_all_day_series_are_dates_regardless_of_the_zone(owner: Api, calendar: dict[str, Any]) -> None:
    create(
        owner,
        calendar,
        start="2026-10-07T00:00:00Z",
        end="2026-10-07T00:00:00Z",
        all_day=True,
        rrule="FREQ=WEEKLY;BYDAY=WE",
        timezone="Pacific/Auckland",
    )
    starts = occurrence_starts(owner, calendar, "2026-10-01T00:00:00Z", "2026-10-16T00:00:00Z")
    assert starts == ["2026-10-07T00:00:00Z", "2026-10-14T00:00:00Z"]


def test_unknown_zones_are_rejected(owner: Api, calendar: dict[str, Any]) -> None:
    res = owner.post(
        f"/calendars/{calendar['id']}/events",
        {
            "title": "x",
            "start": "2026-10-07T10:00:00Z",
            "end": "2026-10-07T11:00:00Z",
            "timezone": "Mars/Olympus",
        },
    )
    assert res.status_code == 422


def test_the_zone_only_changes_along_with_the_schedule(owner: Api, calendar: dict[str, Any]) -> None:
    event = create(
        owner, calendar, start="2026-10-07T10:00:00Z", end="2026-10-07T11:00:00Z", rrule="FREQ=WEEKLY", timezone=BERLIN
    )
    # Someone in another zone edits the title only: the series stays where it was planned.
    res = owner.patch(f"/events/{event['id']}", {"title": "Renamed", "timezone": "America/New_York"})
    assert res.json()["timezone"] == BERLIN
    # A new time from that zone brings the zone along.
    res = owner.patch(
        f"/events/{event['id']}",
        {
            "start": "2026-10-07T14:00:00Z",
            "end": "2026-10-07T15:00:00Z",
            "timezone": "America/New_York",
        },
    )
    assert res.json()["timezone"] == "America/New_York"


def test_ical_export_names_the_zone(owner: Api, calendar: dict[str, Any]) -> None:
    event = create(
        owner, calendar, start="2026-10-19T07:00:00Z", end="2026-10-19T08:00:00Z", rrule="FREQ=WEEKLY", timezone=BERLIN
    )
    text = serialize_event_ical(Event.objects.get(id=event["id"]))
    assert "DTSTART;TZID=Europe/Berlin:20261019T090000" in text
    assert "BEGIN:VTIMEZONE" in text
