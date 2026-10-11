"""
Each user's reminders before events, delivered as notifications.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.models import Event, Notification, User
from core.services.reminders import deliver_due_reminders
from core.tests.test_approval_workflow import iso, world  # noqa: F401

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 8, 50, tzinfo=timezone.utc)
NINE = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)


def create(world, **fields):
    data = {"title": "Meeting", "start": iso(NINE), "end": iso(NINE + timedelta(hours=1)), "timezone": "UTC", **fields}
    res = world["api"]["owner"].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    return res.json()


def remind(world, event, minutes, user="owner"):
    return world["api"][user].client.put(
        f"/api/events/{event['id']}/reminders", {"minutes": minutes}, content_type="application/json"
    )


def reminders_of(world, user="owner"):
    return list(
        Notification.objects.filter(user=world["users"][user], type="event_reminder").values_list("data__start", flat=True)
    )


def test_reminders_are_set_per_user(world):
    event = create(world)
    assert remind(world, event, [30, 15, 15, -5]).json() == {"minutes": [15, 30]}
    # Viewers may be reminded too; it concerns only them.
    world["api"]["owner"].post(f"/calendars/{world['cal']['id']}/members", {"user_id": str(world["users"]["outsider"].id), "role": "viewer"})
    assert remind(world, event, [60], "outsider").json() == {"minutes": [60]}
    assert world["api"]["owner"].get(f"/events/{event['id']}/reminders").json() == {"minutes": [15, 30]}
    assert world["api"]["outsider"].get(f"/events/{event['id']}/reminders").json() == {"minutes": [60]}
    assert remind(world, event, [5], "other").status_code == 200  # contributor, sees the event


def test_due_reminders_are_delivered_once(world):
    event = create(world)
    remind(world, event, [15, 5])
    delivered = deliver_due_reminders(now=NOW)
    # 15 minutes before 09:00 has passed at 08:50, 5 minutes before hasn't.
    assert [(d["event_id"], d["minutes_before"]) for d in delivered] == [(event["id"], 15)]
    assert deliver_due_reminders(now=NOW) == []
    assert [d["minutes_before"] for d in deliver_due_reminders(now=NOW + timedelta(minutes=6))] == [5]
    assert len(reminders_of(world)) == 2


def test_missed_reminders_go_out_shortly_after_the_start_only(world):
    event = create(world)
    remind(world, event, [15])
    assert deliver_due_reminders(now=NINE + timedelta(hours=1)) == []
    assert len(deliver_due_reminders(now=NINE + timedelta(minutes=10))) == 1


def test_every_occurrence_of_a_series_is_reminded_of(world):
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    remind(world, event, [15])
    for day in range(3):
        assert len(deliver_due_reminders(now=NOW + timedelta(days=day))) == 1
    assert deliver_due_reminders(now=NOW + timedelta(days=3)) == []


def test_changed_occurrences_are_reminded_of_at_their_new_time(world):
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    remind(world, event, [15])
    second = NINE + timedelta(days=1)
    url = f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this"
    override = world["api"]["owner"].patch(url, {"start": iso(second + timedelta(hours=2)), "end": iso(second + timedelta(hours=3))}).json()
    assert deliver_due_reminders(now=NOW + timedelta(days=1)) == []
    delivered = deliver_due_reminders(now=NOW + timedelta(days=1, hours=2))
    assert [d["event_id"] for d in delivered] == [override["id"]]


def test_cancelled_and_unreachable_events_are_not_reminded_of(world):
    event = create(world)
    remind(world, event, [15])
    Event.objects.filter(id=event["id"]).update(status="cancelled")
    assert deliver_due_reminders(now=NOW) == []
    Event.objects.filter(id=event["id"]).update(status="confirmed")
    remind(world, event, [15], "other")
    world["api"]["owner"].delete(f"/calendars/{world['cal']['id']}/members/{world['users']['other'].id}")
    deliver_due_reminders(now=NOW)
    # The owner is reminded; the member who left the calendar isn't.
    assert len(reminders_of(world)) == 1 and reminders_of(world, "other") == []


def test_all_day_events_are_reminded_of_in_the_users_zone(world):
    User.objects.filter(id=world["users"]["owner"].id).update(timezone="Europe/Berlin")
    day = datetime(2030, 1, 8, tzinfo=timezone.utc)
    event = create(world, start=iso(day), end=iso(day), all_day=True)
    # The day before at 09:00 in Berlin, which is 08:00 UTC.
    remind(world, event, [15 * 60])
    assert deliver_due_reminders(now=datetime(2030, 1, 7, 7, 59, tzinfo=timezone.utc)) == []
    assert len(deliver_due_reminders(now=datetime(2030, 1, 7, 8, 0, tzinfo=timezone.utc))) == 1


def test_the_unread_count_delivers_due_reminders(world, monkeypatch):
    import core.services.reminders as reminders

    event = create(world)
    remind(world, event, [15])
    monkeypatch.setattr(reminders, "datetime", type("FrozenNow", (datetime,), {"now": staticmethod(lambda tz=None: NOW)}))
    body = world["api"]["owner"].get("/notifications/unread-count").json()
    assert body["count"] == 1
    assert [r["title"] for r in body["reminders"]] == ["Meeting"]
