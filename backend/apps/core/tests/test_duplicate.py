"""
Duplicating an event: a copy at another time or in another calendar, made with the checks of any new event.
"""

from datetime import timedelta
from typing import Any

import pytest
from django.core import mail as django_mail
from django.core.files.uploadedfile import SimpleUploadedFile
from pytest_django.fixtures import Settings

from apps.core.models import CalendarMember, Event, EventActivity, EventAttachment, EventReminder
from apps.core.services import attachments
from apps.core.tests.helpers import BASE, Api, Response, World, iso, make_user

pytestmark = pytest.mark.django_db

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
PDF = b"%PDF-1.7\n%%EOF\n"


def create(world: World, user: str = "owner", calendar_id: str | None = None, **fields: Any) -> dict[str, Any]:
    data = {"title": "Meeting", "start": iso(BASE), "end": iso(BASE + 2 * HOUR), "timezone": "UTC", **fields}
    res = world["api"][user].post(f"/calendars/{calendar_id or world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def duplicate(api: Api, event_id: str, calendar_id: str, start: Any, **extra: Any) -> Response:
    return api.post(f"/events/{event_id}/duplicate", {"calendar_id": calendar_id, "start": iso(start), **extra})


def copied(res: Response) -> dict[str, Any]:
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def test_a_copy_at_another_time_keeps_what_the_event_is(world: World) -> None:
    category = world["api"]["owner"].post(f"/calendars/{world['cal']['id']}/categories", {"name": "Team"}).json()
    room = world["resource"]("Beamer", requires_approval=False)
    hall = world["resource"]("Hall", requires_approval=False, is_location=True)
    source = create(
        world,
        title="Planning",
        description="Agenda",
        category_id=category["id"],
        resource_id=room["id"],
        location_resource_id=hall["id"],
        show_as="out_of_office",
        timezone="Europe/Berlin",
    )
    copy = copied(duplicate(world["api"]["full"], source["id"], world["cal"]["id"], BASE + 3 * DAY))
    assert copy["id"] != source["id"]
    assert copy["uid"] != source["uid"]
    assert (copy["start"], copy["end"]) == (
        iso(BASE + 3 * DAY).replace("+00:00", "Z"),
        iso(BASE + 3 * DAY + 2 * HOUR).replace("+00:00", "Z"),
    )
    for field in (
        "title",
        "description",
        "category_id",
        "resource_id",
        "location_resource_id",
        "location",
        "show_as",
        "timezone",
    ):
        assert copy[field] == source[field], field
    # The one who copied it made it.
    assert copy["creator_id"] == str(world["users"]["full"].id)
    assert EventActivity.objects.filter(event_id=copy["id"], action="created").exists()
    # The original is as it was.
    assert Event.objects.filter(calendar_id=world["cal"]["id"]).count() == 2


def test_a_copy_into_another_calendar_takes_only_what_that_calendar_has(world: World) -> None:
    api = world["api"]["owner"]
    team = api.post(f"/calendars/{world['cal']['id']}/categories", {"name": "Team"}).json()
    room = world["resource"]("Beamer", requires_approval=False)
    hall = world["resource"]("Hall", requires_approval=False, is_location=True)
    other = api.post("/calendars", {"name": "Other"}).json()
    their_team = api.post(f"/calendars/{other['id']}/categories", {"name": "team"}).json()
    source = create(world, category_id=team["id"], resource_id=room["id"], location_resource_id=hall["id"])
    copy = copied(duplicate(api, source["id"], other["id"], BASE))
    assert copy["calendar_id"] == other["id"]
    # A category of the same name stands in; resources are the other calendar's own.
    assert copy["category_id"] == their_team["id"]
    assert copy["resource_id"] is None
    assert copy["location_resource_id"] is None
    assert copy["location"] == "Hall"

    lonely = create(
        world, category_id=api.post(f"/calendars/{world['cal']['id']}/categories", {"name": "Solo"}).json()["id"]
    )
    assert copied(duplicate(api, lonely["id"], other["id"], BASE))["category_id"] is None


def test_resources_no_longer_offered_are_left_out(world: World) -> None:
    api = world["api"]["owner"]
    room = world["resource"]("Beamer", requires_approval=False)
    source = create(world, resource_id=room["id"])
    api.patch(f"/calendars/{world['cal']['id']}/resources/{room['id']}", {"is_active": False})
    assert copied(duplicate(api, source["id"], world["cal"]["id"], BASE + DAY))["resource_id"] is None


def test_a_copied_booking_is_asked_for_again(world: World) -> None:
    room = world["resource"]("Room")
    booking = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{booking['id']}/approve")
    copy = copied(duplicate(world["api"]["booker"], booking["id"], world["cal"]["id"], BASE + DAY))
    assert copy["status"] == "pending"
    assert copy["resource_id"] == room["id"]


def test_a_copy_that_conflicts_with_an_approved_booking_is_refused(world: World) -> None:
    room = world["resource"]("Room")
    booking = world["book"](world["api"]["booker"], room["id"]).json()
    world["api"]["owner"].post(f"/events/{booking['id']}/approve")
    # The owner's copy is approved right away, and would take the room twice at the same time.
    res = duplicate(world["api"]["owner"], booking["id"], world["cal"]["id"], BASE)
    assert res.status_code == 409


def test_a_series_is_copied_as_a_series_with_its_end_moved_along(world: World) -> None:
    api = world["api"]["owner"]
    until = (BASE + 2 * DAY).strftime("%Y%m%dT%H%M%SZ")
    series = create(world, rrule=f"FREQ=DAILY;UNTIL={until}", show_recurrence_count=True)
    second = iso(BASE + DAY).replace("+", "%2B")
    api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"title": "Changed"})
    api.delete(f"/events/{series['id']}/occurrences/{iso(BASE + 2 * DAY).replace('+', '%2B')}?scope=this")
    copy = copied(duplicate(api, series["id"], world["cal"]["id"], BASE + 7 * DAY))
    assert copy["rrule"] == f"FREQ=DAILY;UNTIL={(BASE + 9 * DAY).strftime('%Y%m%dT%H%M%SZ')}"
    assert copy["show_recurrence_count"] is True
    copied_event = Event.objects.get(id=copy["id"])
    # Its own changes and removals stay with the original.
    assert copied_event.exdates == []
    assert not copied_event.overrides.exists()
    url = f"/calendars/{world['cal']['id']}/events?start={iso(BASE + 7 * DAY)}&end={iso(BASE + 14 * DAY)}"
    titles = [o["title"] for o in api.get(url.replace("+", "%2B")).json()]
    assert titles == ["Meeting", "Meeting", "Meeting"]


def test_a_counted_series_keeps_its_count(world: World) -> None:
    series = create(world, rrule="FREQ=WEEKLY;COUNT=4")
    copy = copied(duplicate(world["api"]["owner"], series["id"], world["cal"]["id"], BASE + 2 * DAY))
    assert copy["rrule"] == "FREQ=WEEKLY;COUNT=4"


def test_an_all_day_series_moves_its_end_by_days(world: World) -> None:
    day = BASE.replace(hour=0)
    series = create(world, start=iso(day), end=iso(day), all_day=True, rrule="FREQ=DAILY;UNTIL=20300109")
    copy = copied(duplicate(world["api"]["owner"], series["id"], world["cal"]["id"], day + 10 * DAY))
    assert copy["rrule"] == "FREQ=DAILY;UNTIL=20300119"


def test_a_changed_occurrence_is_copied_as_a_single_event(world: World) -> None:
    api = world["api"]["owner"]
    series = create(world, rrule="FREQ=DAILY;COUNT=3")
    second = iso(BASE + DAY).replace("+", "%2B")
    changed = api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"title": "Special"}).json()
    copy = copied(duplicate(api, changed["id"], world["cal"]["id"], BASE + 5 * DAY))
    assert (copy["title"], copy["rrule"], copy["parent_id"]) == ("Special", None, None)


def test_all_day_events_stay_whole_days(world: World) -> None:
    day = BASE.replace(hour=0)
    source = create(world, start=iso(day), end=iso(day + DAY), all_day=True)
    # A start with a time of day (e.g. from another zone) lands on that day's midnight.
    copy = copied(duplicate(world["api"]["owner"], source["id"], world["cal"]["id"], day + 3 * DAY + 5 * HOUR))
    assert copy["all_day"] is True
    assert copy["start"].startswith((day + 3 * DAY).date().isoformat() + "T00:00:00")
    assert copy["end"].startswith((day + 4 * DAY).date().isoformat() + "T00:00:00")


def test_a_calendar_of_all_day_events_takes_no_timed_copy(world: World) -> None:
    api = world["api"]["owner"]
    days_only = api.post("/calendars", {"name": "Holidays"}).json()
    api.patch(f"/calendars/{days_only['id']}", {"force_all_day": True})
    res = duplicate(api, create(world)["id"], days_only["id"], BASE)
    assert res.status_code == 422
    assert res.json()["detail"] == "This calendar only allows all-day events"


# ---------------------------------------------------------------------------
# Who may copy what where
# ---------------------------------------------------------------------------


def test_a_reader_copies_into_a_calendar_of_their_own(world: World) -> None:
    reader = make_user("reader")
    CalendarMember.objects.create(calendar_id=world["cal"]["id"], user=reader, role="read")
    api = Api(reader)
    source = create(world)
    res = duplicate(api, source["id"], world["cal"]["id"], BASE + DAY)
    assert res.status_code == 403
    assert res.json()["detail"] == "You do not have permission to create events"
    mine = api.post("/calendars", {"name": "Mine"}).json()
    assert copied(duplicate(api, source["id"], mine["id"], BASE))["calendar_id"] == mine["id"]


def test_what_one_doesnt_see_can_t_be_copied(world: World) -> None:
    source = create(world)
    outsider = world["api"]["outsider"]
    mine = outsider.post("/calendars", {"name": "Mine"}).json()
    assert duplicate(outsider, source["id"], mine["id"], BASE).status_code == 404
    # A pending booking is the booker's, the approvers' and the participants' to see.
    room = world["resource"]("Room")
    booking = world["book"](world["api"]["booker"], room["id"]).json()
    assert duplicate(world["api"]["other"], booking["id"], world["cal"]["id"], BASE + DAY).status_code == 404


def test_nothing_is_copied_into_a_calendar_one_isnt_in(world: World) -> None:
    foreign = world["api"]["outsider"].post("/calendars", {"name": "Foreign"}).json()
    res = duplicate(world["api"]["owner"], create(world)["id"], foreign["id"], BASE)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Participants, reminders, attachments
# ---------------------------------------------------------------------------


def participant_emails(event_id: str) -> list[str]:
    return sorted(Event.objects.get(id=event_id).participants.values_list("email", flat=True))


def test_participants_come_along_only_when_asked_and_are_invited_anew(world: World) -> None:
    booker = world["users"]["booker"]
    full = world["users"]["full"]
    source = create(
        world,
        participants=[{"user_id": str(booker.id)}, {"user_id": str(full.id)}, {"email": "guest@example.org"}],
    )
    world["api"]["booker"].patch(f"/events/{source['id']}/participants/me", {"status": "accepted"})
    api = world["api"]["full"]

    alone = copied(duplicate(api, source["id"], world["cal"]["id"], BASE + DAY))
    assert participant_emails(alone["id"]) == []

    django_mail.outbox.clear()
    invited = copied(duplicate(api, source["id"], world["cal"]["id"], BASE + 2 * DAY, invite_participants=True))
    # The one copying it organizes the copy and isn't among its participants.
    assert participant_emails(invited["id"]) == sorted([booker.email, "guest@example.org"])
    statuses = set(Event.objects.get(id=invited["id"]).participants.values_list("status", flat=True))
    assert statuses == {"needs_action"}
    assert sorted(address for m in django_mail.outbox for address in m.to) == sorted(
        [booker.email, "guest@example.org"]
    )


def test_one_s_own_reminders_come_along_not_others(world: World) -> None:
    source = create(world)
    world["api"]["owner"].put(f"/events/{source['id']}/reminders", {"minutes": [10, 60]})
    world["api"]["full"].put(f"/events/{source['id']}/reminders", {"minutes": [5]})
    copy = copied(duplicate(world["api"]["owner"], source["id"], world["cal"]["id"], BASE + DAY))
    reminders = EventReminder.objects.filter(event_id=copy["id"])
    assert sorted((r.user_id, r.minutes_before) for r in reminders) == [
        (world["users"]["owner"].id, 10),
        (world["users"]["owner"].id, 60),
    ]


def upload(api: Api, event_id: str, name: str, content: bytes) -> dict[str, Any]:
    res = api.client.post(f"/api/events/{event_id}/attachments/files", {"file": SimpleUploadedFile(name, content)})
    assert res.status_code == 200, res.content
    added: dict[str, Any] = res.json()
    return added


def test_attachments_come_along_as_copies_of_their_own(world: World) -> None:
    api = world["api"]["owner"]
    source = create(world)
    original = upload(api, source["id"], "Agenda.pdf", PDF)
    api.post(f"/events/{source['id']}/attachments/links", {"url": "https://example.org", "name": "Site"})
    copy = copied(duplicate(api, source["id"], world["cal"]["id"], BASE + DAY))
    copies = list(EventAttachment.objects.filter(event_id=copy["id"]))
    assert [(a.kind, a.name) for a in copies] == [("file", "Agenda.pdf"), ("link", "Site")]
    copied_file = copies[0]
    assert copied_file.id != original["id"]
    assert attachments.file_path(copied_file).read_bytes() == PDF
    # Removing the original's file leaves the copy's.
    attachments.file_path(EventAttachment.objects.get(id=original["id"])).unlink()
    assert api.client.get(f"/api/attachments/{copied_file.id}/download").status_code == 200


def test_a_copy_needs_room_for_its_files(world: World, settings: Settings) -> None:
    settings.ATTACHMENT_CALENDAR_QUOTA = len(PDF) + 5
    api = world["api"]["owner"]
    source = create(world)
    upload(api, source["id"], "Agenda.pdf", PDF)
    res = duplicate(api, source["id"], world["cal"]["id"], BASE + DAY)
    assert res.status_code == 413
    # Nothing is left of the copy.
    assert Event.objects.filter(calendar_id=world["cal"]["id"]).count() == 1


def test_a_file_whose_content_is_gone_is_left_out_of_the_copy(world: World) -> None:
    api = world["api"]["owner"]
    source = create(world)
    original = upload(api, source["id"], "Agenda.pdf", PDF)
    attachments.file_path(EventAttachment.objects.get(id=original["id"])).unlink()
    copy = copied(duplicate(api, source["id"], world["cal"]["id"], BASE + DAY))
    assert not EventAttachment.objects.filter(event_id=copy["id"]).exists()
