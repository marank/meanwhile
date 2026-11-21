"""
CalDAV must not offer a way around the booking approval workflow or calendar permissions.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from radicale import config
from radicale import item as radicale_item

from apps.core.caldav.rights import Rights
from apps.core.caldav.storage import Collection, acting_as
from apps.core.models import Calendar, CalendarGroup, Event, UserGroup
from apps.core.tests.helpers import BASE, World

pytestmark = pytest.mark.django_db


def ics(uid: str, start: datetime, end: datetime, summary: str = "Booking") -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTAMP:{start.strftime(fmt)}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\nDTEND:{end.strftime(fmt)}\r\n"
        f"SUMMARY:{summary}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.fixture(autouse=True)
def as_owner(world: World) -> Iterator[None]:
    # Radicale runs every request for the logged-in user; these tests write as the calendar owner.
    with acting_as(world["users"]["owner"].email):
        yield


def collection(world: World) -> Collection:
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    owner = world["users"]["owner"]
    return Collection(config.load(), f"/{owner.email}/{calendar.id}/", calendar=calendar, user=owner)


def upload(
    world: World, event: dict[str, Any], start: datetime = BASE, hours: int = 1, summary: str = "Booking"
) -> None:
    coll = collection(world)
    text = ics(event["uid"], start, start + timedelta(hours=hours), summary)
    item = radicale_item.Item(collection=coll, text=text)
    coll.upload(f"{event['uid']}.ics", item)


def booking(
    world: World, status: str = "pending", requires_approval: bool = True, start: datetime = BASE
) -> dict[str, Any]:
    room = world["resource"](
        "Room " + status + str(requires_approval) + start.isoformat(), requires_approval=requires_approval
    )
    event: dict[str, Any] = world["book"](world["api"]["booker"], room["id"], start=start).json()
    if status == "approved":
        world["api"]["owner"].post(f"/events/{event['id']}/approve")
    elif status == "rejected":
        world["api"]["owner"].post(f"/events/{event['id']}/reject")
    elif status == "cancelled":
        world["api"]["booker"].post(f"/events/{event['id']}/cancel")
    return event


# Radicale reports a refused write as a PermissionError, which arrives as this ValueError.
FORBIDDEN = r"\[Errno 13\]"


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
def test_hidden_bookings_cannot_be_changed(world: World, status: str) -> None:
    event = booking(world, status)
    with pytest.raises(ValueError, match=FORBIDDEN):
        upload(world, event, summary="Hijacked")
    stored = Event.objects.get(id=event["id"])
    assert stored.status == status
    assert stored.title == "Booking"


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
def test_hidden_bookings_cannot_be_deleted(world: World, status: str) -> None:
    event = booking(world, status)
    collection(world).delete(f"{event['uid']}.ics")
    assert Event.objects.filter(id=event["id"]).exists()


def test_renaming_an_approved_booking_keeps_its_status(world: World) -> None:
    event = booking(world, "approved")
    upload(world, event, summary="Renamed")
    stored = Event.objects.get(id=event["id"])
    assert stored.title == "Renamed"
    assert stored.status == "approved"


def test_approved_booking_cannot_be_rescheduled_via_caldav(world: World) -> None:
    event = booking(world, "approved")
    with pytest.raises(ValueError, match=FORBIDDEN):
        upload(world, event, start=BASE + timedelta(days=1))
    assert Event.objects.get(id=event["id"]).start == BASE


def test_rescheduling_without_approval_checks_conflicts(world: World) -> None:
    beamer = world["resource"]("Beamer", requires_approval=False)
    world["book"](world["api"]["booker"], beamer["id"])
    later = world["book"](world["api"]["booker"], beamer["id"], start=BASE + timedelta(hours=2)).json()

    with pytest.raises(ValueError, match="conflicts with an approved booking"):
        upload(world, later, start=BASE + timedelta(minutes=30))
    assert Event.objects.get(id=later["id"]).start == BASE + timedelta(hours=2)

    upload(world, later, start=BASE + timedelta(hours=1))
    assert Event.objects.get(id=later["id"]).start == BASE + timedelta(hours=1)


def test_plain_events_can_still_be_edited_and_created(world: World) -> None:
    event = world["book"](world["api"]["booker"], None).json()
    upload(world, event, start=BASE + timedelta(days=3), summary="Moved")
    stored = Event.objects.get(id=event["id"])
    assert (stored.title, stored.start, stored.status) == ("Moved", BASE + timedelta(days=3), "confirmed")

    upload(world, {"uid": "new-from-client"}, summary="From phone")
    assert Event.objects.get(uid="new-from-client").status == "confirmed"


def test_caldav_rights_follow_calendar_membership(world: World) -> None:
    rights = Rights(config.load())
    u = world["users"]
    path = f"/{u['owner'].email}/{world['cal']['id']}/"
    assert rights.authorization(u["owner"].email, set(), path) == "RWrw"
    assert rights.authorization(u["booker"].email, set(), path) == "RWrw"
    assert rights.authorization(u["outsider"].email, set(), path) == ""

    world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/members", {"user_id": str(u["outsider"].id), "role": "read"}
    )
    assert rights.authorization(u["outsider"].email, set(), path) == "Rr"


def test_caldav_rights_include_group_access(world: World) -> None:
    u = world["users"]
    group = UserGroup.objects.create(name="Crew")
    u["outsider"].groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role="own")
    path = f"/{u['owner'].email}/{world['cal']['id']}/"
    assert Rights(config.load()).authorization(u["outsider"].email, set(), path) == "RWrw"


def test_events_from_clients_keep_their_time_zone(world: World) -> None:
    coll = collection(world)
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VEVENT\r\nUID:series-from-phone\r\nDTSTAMP:20261001T000000Z\r\n"
        "DTSTART;TZID=Europe/Berlin:20261019T090000\r\nDTEND;TZID=Europe/Berlin:20261019T100000\r\n"
        "RRULE:FREQ=WEEKLY\r\nSUMMARY:Standup\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    coll.upload("series-from-phone.ics", radicale_item.Item(collection=coll, text=text))
    stored = Event.objects.get(uid="series-from-phone")
    assert stored.timezone == "Europe/Berlin"
    assert stored.start.isoformat() == "2026-10-19T07:00:00+00:00"
