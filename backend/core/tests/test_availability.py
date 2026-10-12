"""
Availability: when people and resources are taken, without what they are taken by.
"""

from datetime import timedelta

import pytest

from core.tests.test_approval_workflow import BASE, iso, world  # noqa: F401

pytestmark = pytest.mark.django_db

HOUR = timedelta(hours=1)


def create(world, user="owner", start=BASE, hours=1, **fields):
    data = {"title": "Secret", "start": iso(start), "end": iso(start + hours * HOUR), "timezone": "UTC", **fields}
    res = world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    return res.json()


def availability(world, user="owner", users=(), resources=(), exclude=None, start=BASE - HOUR, end=BASE + 24 * HOUR):
    data = {
        "start": iso(start),
        "end": iso(end),
        "user_ids": [world["users"][u].id for u in users],
        "resource_ids": list(resources),
        "exclude_event_id": exclude,
    }
    res = world["api"][user].post("/availability", data)
    assert res.status_code == 200, res.content
    return res.json()


def periods(entry):
    return [(p["start"][11:16], p["end"][11:16], p["tentative"]) for p in entry["busy"]]


def test_a_users_busy_times_without_details(world):
    create(world, "booker")
    create(world, "booker", start=BASE + 30 * timedelta(minutes=1))  # overlaps, merged
    create(world, "booker", start=BASE + 3 * HOUR)
    body = availability(world, users=["booker"])
    assert periods(body["users"][0]) == [("09:00", "10:30", False), ("12:00", "13:00", False)]
    assert "Secret" not in str(body)


def test_invitations_count_by_their_answer(world):
    booker = world["users"]["booker"]
    invited = create(world, "owner", participants=[{"user_id": str(booker.id)}])
    assert periods(availability(world, users=["booker"])["users"][0]) == [("09:00", "10:00", True)]
    world["api"]["booker"].client.patch(
        f"/api/events/{invited['id']}/participants/me", {"status": "accepted"}, content_type="application/json"
    )
    assert periods(availability(world, users=["booker"])["users"][0]) == [("09:00", "10:00", False)]
    world["api"]["booker"].client.patch(
        f"/api/events/{invited['id']}/participants/me", {"status": "declined"}, content_type="application/json"
    )
    assert periods(availability(world, users=["booker"])["users"][0]) == []


def test_series_and_their_exceptions(world):
    series = create(world, "booker", rrule="FREQ=HOURLY;COUNT=3")
    url = f"/events/{series['id']}/occurrences/{iso(BASE + HOUR).replace('+', '%2B')}?scope=this"
    world["api"]["booker"].delete(url)
    assert periods(availability(world, users=["booker"])["users"][0]) == [("09:00", "10:00", False), ("11:00", "12:00", False)]
    # Planning the series itself, it doesn't block itself.
    assert availability(world, users=["booker"], exclude=series["id"])["users"][0]["busy"] == []


def test_resources_for_members_of_their_calendar(world):
    room = world["resource"]("Room", requires_approval=True)
    world["book"](world["api"]["booker"], room["id"])
    entry = availability(world, resources=[room["id"]])["resources"][0]
    assert entry["name"] == "Room" and periods(entry) == [("09:00", "10:00", True)]
    assert availability(world, "outsider", resources=[room["id"]])["resources"] == []


def test_ranges_are_limited(world):
    res = world["api"]["owner"].post("/availability", {"start": iso(BASE), "end": iso(BASE + timedelta(days=90))})
    assert res.status_code == 422
