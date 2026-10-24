"""
Changing and removing single occurrences of a series through the API.
"""

from datetime import timedelta

import pytest

from core.models import Event
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)


@pytest.fixture
def series(world):
    """Five daily meetings from BASE (Monday 09:00 UTC) on, created by the owner."""
    owner = world["api"]["owner"]
    res = owner.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Daily",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "rrule": "FREQ=DAILY;COUNT=5",
            "timezone": "UTC",
        },
    )
    assert res.status_code == 200, res.content
    return res.json()


def occurrences(world, user="owner"):
    res = world["api"][user].get(
        f"/events?start={iso(BASE - DAY)}&end={iso(BASE + 30 * DAY)}&calendar_ids={world['cal']['id']}".replace(
            "+", "%2B"
        )
    )
    assert res.status_code == 200, res.content
    return res.json()


def summary(world):
    return [(o["start"][:16], o["title"]) for o in occurrences(world)]


def occurrence_url(series, start, scope="this"):
    return f"/events/{series['id']}/occurrences/{iso(start).replace('+', '%2B')}?scope={scope}"


def test_changing_one_occurrence(world, series):
    owner = world["api"]["owner"]
    third = BASE + 2 * DAY
    res = owner.patch(
        occurrence_url(series, third),
        {"title": "Moved", "start": iso(third + timedelta(hours=3)), "end": iso(third + timedelta(hours=4))},
    )
    assert res.status_code == 200, res.content
    override = res.json()
    assert override["parent_id"] == series["id"] and override["recurrence_id"].startswith("2030-01-09T09:00")

    assert summary(world) == [
        ("2030-01-07T09:00", "Daily"),
        ("2030-01-08T09:00", "Daily"),
        ("2030-01-09T12:00", "Moved"),
        ("2030-01-10T09:00", "Daily"),
        ("2030-01-11T09:00", "Daily"),
    ]
    moved = [o for o in occurrences(world) if o["title"] == "Moved"][0]
    assert moved["event_id"] == override["id"] and moved["series_id"] == series["id"] and moved["is_recurring"]
    plain = occurrences(world)[0]
    assert plain["series_id"] == series["id"] and plain["recurrence_id"].startswith("2030-01-07T09:00")

    # Changing it again edits the same occurrence.
    res = owner.patch(occurrence_url(series, third), {"title": "Moved again"})
    assert res.json()["id"] == override["id"]
    # So does editing the changed occurrence itself; it can't get a recurrence of its own.
    assert owner.patch(f"/events/{override['id']}", {"title": "Edited"}).status_code == 200
    assert owner.patch(f"/events/{override['id']}", {"rrule": "FREQ=DAILY"}).status_code == 422


def test_removing_one_occurrence(world, series):
    owner = world["api"]["owner"]
    assert owner.delete(occurrence_url(series, BASE + DAY)).status_code == 200
    assert [s for s, _ in summary(world)] == [
        "2030-01-07T09:00",
        "2030-01-09T09:00",
        "2030-01-10T09:00",
        "2030-01-11T09:00",
    ]
    # It is gone for good: asking for it again finds nothing.
    assert owner.delete(occurrence_url(series, BASE + DAY)).status_code == 404


def test_deleting_a_changed_occurrence_removes_it(world, series):
    owner = world["api"]["owner"]
    override = owner.patch(occurrence_url(series, BASE + DAY), {"title": "Special"}).json()
    assert owner.delete(f"/events/{override['id']}").status_code == 200
    assert "2030-01-08T09:00" not in [s for s, _ in summary(world)]
    assert Event.objects.get(id=series["id"]).exdates == [iso(BASE + DAY)]


def test_changing_this_and_following(world, series):
    owner = world["api"]["owner"]
    third = BASE + 2 * DAY
    res = owner.patch(
        occurrence_url(series, third, "following"),
        {"title": "Later", "start": iso(third + timedelta(hours=1)), "end": iso(third + timedelta(hours=2))},
    )
    assert res.status_code == 200, res.content
    following = res.json()
    assert following["id"] != series["id"] and following["rrule"] == "FREQ=DAILY;COUNT=3"
    assert summary(world) == [
        ("2030-01-07T09:00", "Daily"),
        ("2030-01-08T09:00", "Daily"),
        ("2030-01-09T10:00", "Later"),
        ("2030-01-10T10:00", "Later"),
        ("2030-01-11T10:00", "Later"),
    ]
    assert Event.objects.get(id=series["id"]).rrule == "FREQ=DAILY;UNTIL=20300109T085959Z"


def test_following_from_the_first_occurrence_changes_the_series(world, series):
    owner = world["api"]["owner"]
    res = owner.patch(occurrence_url(series, BASE, "following"), {"title": "Renamed"})
    assert res.json()["id"] == series["id"]
    assert {t for _, t in summary(world)} == {"Renamed"}


def test_moving_all_occurrences_keeps_the_changed_ones(world, series):
    owner = world["api"]["owner"]
    fourth = BASE + 3 * DAY
    owner.patch(occurrence_url(series, fourth), {"title": "Special"})
    owner.delete(occurrence_url(series, BASE + DAY))
    third = BASE + 2 * DAY
    res = owner.patch(
        occurrence_url(series, third, "all"),
        {"start": iso(third + timedelta(hours=1)), "end": iso(third + timedelta(hours=2))},
    )
    assert res.json()["id"] == series["id"]
    assert summary(world) == [
        ("2030-01-07T10:00", "Daily"),
        ("2030-01-09T10:00", "Daily"),
        ("2030-01-10T09:00", "Special"),
        ("2030-01-11T10:00", "Daily"),
    ]
    stored = Event.objects.get(id=series["id"])
    assert stored.exdates == [iso(BASE + DAY + timedelta(hours=1))]
    assert stored.overrides.get().recurrence_id == fourth + timedelta(hours=1)


def test_removing_this_and_following(world, series):
    owner = world["api"]["owner"]
    owner.patch(occurrence_url(series, BASE + 3 * DAY), {"title": "Special"})
    assert owner.delete(occurrence_url(series, BASE + 2 * DAY, "following")).status_code == 200
    assert summary(world) == [("2030-01-07T09:00", "Daily"), ("2030-01-08T09:00", "Daily")]
    assert not Event.objects.filter(parent_id=series["id"]).exists()

    assert owner.delete(occurrence_url(series, BASE, "following")).status_code == 200
    assert not Event.objects.filter(id=series["id"]).exists()


def test_occurrences_must_exist(world, series):
    owner = world["api"]["owner"]
    assert owner.patch(occurrence_url(series, BASE + timedelta(hours=5)), {"title": "x"}).status_code == 404
    assert owner.patch(occurrence_url(series, BASE + 10 * DAY), {"title": "x"}).status_code == 404


def test_only_who_may_edit_the_series_changes_occurrences(world, series):
    booker = world["api"]["booker"]
    assert booker.patch(occurrence_url(series, BASE), {"title": "x"}).status_code == 403
    assert booker.delete(occurrence_url(series, BASE)).status_code == 403


def test_changed_booking_occurrence_needs_approval_again(world):
    room = world["resource"]("Room", requires_approval=True)
    booker = world["api"]["booker"]
    res = booker.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Weekly",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "rrule": "FREQ=WEEKLY;COUNT=3",
            "resource_id": room["id"],
        },
    )
    series = res.json()
    world["api"]["owner"].post(f"/events/{series['id']}/approve")

    second = BASE + 7 * DAY
    res = booker.patch(
        occurrence_url(series, second),
        {"start": iso(second + timedelta(hours=2)), "end": iso(second + timedelta(hours=3))},
    )
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "pending"
    assert Event.objects.get(id=series["id"]).status == "approved"


def test_approving_a_series_approves_its_waiting_occurrences(world):
    room = world["resource"]("Room", requires_approval=True)
    booker = world["api"]["booker"]
    series = booker.post(
        f"/calendars/{world['cal']['id']}/events",
        {
            "title": "Weekly",
            "start": iso(BASE),
            "end": iso(BASE + timedelta(hours=1)),
            "rrule": "FREQ=WEEKLY;COUNT=3",
            "resource_id": room["id"],
        },
    ).json()
    override = booker.patch(occurrence_url(series, BASE + 7 * DAY), {"title": "Second"}).json()
    assert override["status"] == "pending"
    world["api"]["owner"].post(f"/events/{series['id']}/approve")
    assert Event.objects.get(id=override["id"]).status == "approved"


def test_following_from_a_changed_occurrence_the_rule_no_longer_has_is_refused(world, series):
    """A CalDAV client may store a changed occurrence at a time the rule doesn't produce."""
    stray = BASE + 2 * DAY + timedelta(hours=3)
    parent = Event.objects.get(id=series["id"])
    Event.objects.create(
        calendar=parent.calendar,
        creator=parent.creator,
        parent=parent,
        recurrence_id=stray,
        title="Moved by a client",
        start=stray,
        end=stray + timedelta(hours=1),
        timezone="UTC",
    )
    owner = world["api"]["owner"]

    res = owner.patch(occurrence_url(series, stray, "following"), {"title": "Later"})

    assert res.status_code == 422, res.content
    assert Event.objects.get(id=series["id"]).rrule == "FREQ=DAILY;COUNT=5"
    # On its own it can still be changed.
    assert owner.patch(occurrence_url(series, stray, "this"), {"title": "Later"}).status_code == 200
