"""
CalDAV must not offer a way around the booking approval workflow or calendar permissions.
"""

from datetime import timedelta

import pytest
from radicale import item as radicale_item

from core.caldav.rights import Rights
from core.caldav.storage import Collection
from core.models import Calendar, CalendarGroup, Event, UserGroup
from core.tests.test_approval_workflow import BASE, add_default_approver, world  # noqa: F401

pytestmark = pytest.mark.django_db


def ics(uid: str, start, end, summary="Booking") -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTAMP:{start.strftime(fmt)}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\nDTEND:{end.strftime(fmt)}\r\n"
        f"SUMMARY:{summary}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


def collection(world):
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    owner = world["users"]["owner"]
    return Collection(None, f"/{owner.email}/{calendar.id}/", calendar=calendar, user=owner)


def upload(world, event, start=BASE, hours=1, summary="Booking"):
    coll = collection(world)
    text = ics(event["uid"], start, start + timedelta(hours=hours), summary)
    item = radicale_item.Item(collection=coll, text=text)
    return coll.upload(f"{event['uid']}.ics", item)


def booking(world, status="pending", requires_approval=True, start=BASE):
    room = world["resource"]("Room " + status + str(requires_approval) + start.isoformat(), requires_approval=requires_approval)
    event = world["book"](world["api"]["booker"], room["id"], start=start).json()
    if status == "approved":
        world["api"]["owner"].post(f"/events/{event['id']}/approve")
    elif status == "rejected":
        world["api"]["owner"].post(f"/events/{event['id']}/reject")
    elif status == "cancelled":
        world["api"]["booker"].post(f"/events/{event['id']}/cancel")
    return event


def forbidden(exc_info) -> bool:
    return "[Errno 13]" in str(exc_info.value)


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
def test_hidden_bookings_cannot_be_changed(world, status):
    event = booking(world, status)
    with pytest.raises(ValueError) as exc:
        upload(world, event, summary="Hijacked")
    assert forbidden(exc)
    stored = Event.objects.get(id=event["id"])
    assert stored.status == status
    assert stored.title == "Booking"


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
def test_hidden_bookings_cannot_be_deleted(world, status):
    event = booking(world, status)
    collection(world).delete(f"{event['uid']}.ics")
    assert Event.objects.filter(id=event["id"]).exists()


def test_renaming_an_approved_booking_keeps_its_status(world):
    event = booking(world, "approved")
    upload(world, event, summary="Renamed")
    stored = Event.objects.get(id=event["id"])
    assert stored.title == "Renamed"
    assert stored.status == "approved"


def test_approved_booking_cannot_be_rescheduled_via_caldav(world):
    event = booking(world, "approved")
    with pytest.raises(ValueError) as exc:
        upload(world, event, start=BASE + timedelta(days=1))
    assert forbidden(exc)
    assert Event.objects.get(id=event["id"]).start == BASE


def test_rescheduling_without_approval_checks_conflicts(world):
    beamer = world["resource"]("Beamer", requires_approval=False)
    world["book"](world["api"]["booker"], beamer["id"])
    later = world["book"](world["api"]["booker"], beamer["id"], start=BASE + timedelta(hours=2)).json()

    with pytest.raises(ValueError) as exc:
        upload(world, later, start=BASE + timedelta(minutes=30))
    assert not forbidden(exc)
    assert Event.objects.get(id=later["id"]).start == BASE + timedelta(hours=2)

    upload(world, later, start=BASE + timedelta(hours=1))
    assert Event.objects.get(id=later["id"]).start == BASE + timedelta(hours=1)


def test_plain_events_can_still_be_edited_and_created(world):
    event = world["book"](world["api"]["booker"], None).json()
    upload(world, event, start=BASE + timedelta(days=3), summary="Moved")
    stored = Event.objects.get(id=event["id"])
    assert (stored.title, stored.start, stored.status) == ("Moved", BASE + timedelta(days=3), "confirmed")

    upload(world, {"uid": "new-from-client"}, summary="From phone")
    assert Event.objects.get(uid="new-from-client").status == "confirmed"


def test_caldav_rights_follow_calendar_membership(world):
    rights = Rights(None)
    u = world["users"]
    path = f"/{u['owner'].email}/{world['cal']['id']}/"
    assert rights.authorization(u["owner"].email, path) == "RWrw"
    assert rights.authorization(u["booker"].email, path) == "RWrw"
    assert rights.authorization(u["outsider"].email, path) == ""

    world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/members", {"user_id": str(u["outsider"].id), "role": "viewer"}
    )
    assert rights.authorization(u["outsider"].email, path) == "Rr"


def test_caldav_rights_include_group_access(world):
    u = world["users"]
    group = UserGroup.objects.create(name="Crew")
    u["outsider"].groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role="contributor")
    path = f"/{u['owner'].email}/{world['cal']['id']}/"
    assert Rights(None).authorization(u["outsider"].email, path) == "RWrw"
