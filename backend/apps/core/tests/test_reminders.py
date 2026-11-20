"""
Each user's reminders before events, delivered as notifications.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models import Event, EventReminder, Notification, User
from apps.core.services.reminders import deliver_due_reminders
from apps.core.tests.helpers import Response, World, iso

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 8, 50, tzinfo=UTC)
NINE = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


def create(world: World, **fields: Any) -> dict[str, Any]:
    data = {"title": "Meeting", "start": iso(NINE), "end": iso(NINE + timedelta(hours=1)), "timezone": "UTC", **fields}
    res = world["api"]["owner"].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def remind(world: World, event: dict[str, Any], minutes: list[int], user: str = "owner") -> Response:
    return world["api"][user].client.put(
        f"/api/events/{event['id']}/reminders", {"minutes": minutes}, content_type="application/json"
    )


def reminders_of(world: World, user: str = "owner") -> list[str]:
    return list(
        Notification.objects.filter(user=world["users"][user], type="event_reminder").values_list(
            "data__start", flat=True
        )
    )


def test_reminders_are_set_per_user(world: World) -> None:
    event = create(world)
    assert remind(world, event, [30, 15, 15, -5]).json() == {"minutes": [15, 30]}
    # Viewers may be reminded too; it concerns only them.
    world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/members", {"user_id": str(world["users"]["outsider"].id), "role": "read"}
    )
    assert remind(world, event, [60], "outsider").json() == {"minutes": [60]}
    assert world["api"]["owner"].get(f"/events/{event['id']}/reminders").json() == {"minutes": [15, 30]}
    assert world["api"]["outsider"].get(f"/events/{event['id']}/reminders").json() == {"minutes": [60]}
    assert remind(world, event, [5], "other").status_code == 200  # contributor, sees the event


def test_due_reminders_are_delivered_once(world: World) -> None:
    event = create(world)
    remind(world, event, [15, 5])
    delivered = deliver_due_reminders(now=NOW)
    # 15 minutes before 09:00 has passed at 08:50, 5 minutes before hasn't.
    assert [(d["event_id"], d["minutes_before"]) for d in delivered] == [(event["id"], 15)]
    assert deliver_due_reminders(now=NOW) == []
    assert [d["minutes_before"] for d in deliver_due_reminders(now=NOW + timedelta(minutes=6))] == [5]
    assert len(reminders_of(world)) == 2


@pytest.mark.parametrize("found_after_the_start, delivered", [(timedelta(minutes=10), 1), (timedelta(hours=1), 0)])
def test_missed_reminders_go_out_shortly_after_the_start_only(
    world: World, found_after_the_start: timedelta, delivered: int
) -> None:
    event = create(world)
    remind(world, event, [15])
    assert len(deliver_due_reminders(now=NINE + found_after_the_start)) == delivered


def test_every_occurrence_of_a_series_is_reminded_of(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    remind(world, event, [15])
    for day in range(3):
        assert len(deliver_due_reminders(now=NOW + timedelta(days=day))) == 1
    assert deliver_due_reminders(now=NOW + timedelta(days=3)) == []


def test_changed_occurrences_are_reminded_of_at_their_new_time(world: World) -> None:
    event = create(world, rrule="FREQ=DAILY;COUNT=3")
    remind(world, event, [15])
    second = NINE + timedelta(days=1)
    url = f"/events/{event['id']}/occurrences/{iso(second).replace('+', '%2B')}?scope=this"
    override = (
        world["api"]["owner"]
        .patch(url, {"start": iso(second + timedelta(hours=2)), "end": iso(second + timedelta(hours=3))})
        .json()
    )
    assert deliver_due_reminders(now=NOW + timedelta(days=1)) == []
    delivered = deliver_due_reminders(now=NOW + timedelta(days=1, hours=2))
    assert [d["event_id"] for d in delivered] == [override["id"]]


def set_status(event: dict[str, Any], status: str) -> None:
    row = Event.objects.get(id=event["id"])
    row.status = status
    row.save()


def test_cancelled_and_unreachable_events_are_not_reminded_of(world: World) -> None:
    event = create(world)
    remind(world, event, [15])
    set_status(event, "cancelled")
    assert deliver_due_reminders(now=NOW) == []
    # Changed back (saved, as the app does), the event is reminded of again.
    set_status(event, "confirmed")
    remind(world, event, [15], "other")
    world["api"]["owner"].delete(f"/calendars/{world['cal']['id']}/members/{world['users']['other'].id}")
    deliver_due_reminders(now=NOW)
    # The owner is reminded; the member who left the calendar isn't.
    assert len(reminders_of(world)) == 1 and reminders_of(world, "other") == []


def test_all_day_events_are_reminded_of_in_the_users_zone(world: World) -> None:
    User.objects.filter(id=world["users"]["owner"].id).update(timezone="Europe/Berlin")
    day = datetime(2030, 1, 8, tzinfo=UTC)
    event = create(world, start=iso(day), end=iso(day), all_day=True)
    # The day before at 09:00 in Berlin, which is 08:00 UTC.
    remind(world, event, [15 * 60])
    assert deliver_due_reminders(now=datetime(2030, 1, 7, 7, 59, tzinfo=UTC)) == []
    assert len(deliver_due_reminders(now=datetime(2030, 1, 7, 8, 0, tzinfo=UTC))) == 1


def test_setting_a_reminder_does_not_notify(world: World) -> None:
    event = create(world)
    remind(world, event, [15])
    body = world["api"]["owner"].get("/notifications/counts").json()
    assert body["unread"] == 0


def test_a_delivery_works_out_when_the_reminder_is_next_due(world: World) -> None:
    event = create(world, rrule="FREQ=YEARLY;INTERVAL=2")
    remind(world, event, [15])
    reminder = EventReminder.objects.get(event_id=event["id"])
    assert len(deliver_due_reminders(now=NOW)) == 1
    reminder.refresh_from_db()
    assert reminder.next_due_at == NINE.replace(year=2032) - timedelta(minutes=15)

    # Moving the series has it worked out again by the next delivery.
    world["api"]["owner"].patch(
        f"/events/{event['id']}", {"start": iso(NINE + timedelta(hours=1)), "end": iso(NINE + timedelta(hours=2))}
    )
    reminder.refresh_from_db()
    assert reminder.next_due_at <= NOW
    deliver_due_reminders(now=NOW)
    reminder.refresh_from_db()
    assert reminder.next_due_at == NINE.replace(hour=10) - timedelta(minutes=15)


def test_reminders_not_due_cost_nothing(world: World) -> None:
    def run_queries() -> int:
        with CaptureQueriesContext(connection) as captured:
            deliver_due_reminders(now=NOW)
        return len(captured)

    for _ in range(3):
        remind(
            world,
            create(world, start=iso(NINE + timedelta(days=30)), end=iso(NINE + timedelta(days=30, hours=1))),
            [15],
        )
    deliver_due_reminders(now=NOW)  # works out when each is due: in a month
    few = run_queries()
    for _ in range(20):
        remind(
            world,
            create(world, start=iso(NINE + timedelta(days=30)), end=iso(NINE + timedelta(days=30, hours=1))),
            [15],
        )
    deliver_due_reminders(now=NOW)
    assert run_queries() == few


def test_reminders_stay_within_bounds(world: World) -> None:
    from apps.core.services.reminders import MAX_MINUTES_BEFORE, MAX_REMINDERS

    event = create(world)
    asked = [-5, MAX_MINUTES_BEFORE + 1, *range(0, 2 * MAX_REMINDERS * 5, 5)]
    res = remind(world, event, asked)
    assert res.status_code == 200, res.content
    # The ones closest to the start, as many as allowed.
    assert res.json()["minutes"] == list(range(0, MAX_REMINDERS * 5, 5))


def test_caldav_alarms_stay_within_the_same_bounds() -> None:
    from apps.core.caldav.parsing import parse_series
    from apps.core.services.reminders import MAX_REMINDERS

    def alarm(trigger: str) -> str:
        return f"BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:x\r\nTRIGGER:{trigger}\r\nEND:VALARM\r\n"

    alarms = (
        alarm("-P52W")  # a year before: more than the app offers
        + alarm("PT10M")  # after the start
        + "".join(alarm(f"-PT{m}M") for m in range(1, 3 * MAX_REMINDERS))
    )
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:a\r\n"
        "DTSTART:20300107T090000Z\r\nDTEND:20300107T100000Z\r\n" + alarms + "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    series, _ = parse_series(ics)
    assert series["alarms"] == list(range(1, MAX_REMINDERS + 1))
