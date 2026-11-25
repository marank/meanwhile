"""
"Show as" (free, busy, tentative, out of office, working elsewhere): set in the app or by CalDAV clients,
written to iCalendar as TRANSP and Outlook's BUSYSTATUS, and counted by availability.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.test import Client
from radicale import config
from radicale import item as radicale_item

from apps.core.caldav.storage import Collection, acting_as
from apps.core.models import Calendar, Event, EventActivity, FeedToken
from apps.core.services.ical import serialize_event_ical
from apps.core.tests.helpers import BASE, World, iso

pytestmark = pytest.mark.django_db

HOUR = timedelta(hours=1)


def create(world: World, user: str = "owner", start: datetime = BASE, **fields: Any) -> dict[str, Any]:
    data = {"title": "Meeting", "start": iso(start), "end": iso(start + HOUR), "timezone": "UTC", **fields}
    res = world["api"][user].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    event: dict[str, Any] = res.json()
    return event


def occurrences(world: World, user: str = "owner") -> list[dict[str, Any]]:
    url = f"/calendars/{world['cal']['id']}/events?start={iso(BASE - HOUR)}&end={iso(BASE + 48 * HOUR)}"
    res = world["api"][user].get(url.replace("+", "%2B"))
    assert res.status_code == 200, res.content
    listed: list[dict[str, Any]] = res.json()
    return listed


def lines(text: str) -> list[str]:
    """The iCalendar's content lines, unfolded."""
    return text.replace("\r\n ", "").split("\r\n")


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------


def test_new_events_take_up_time_unless_said_otherwise(world: World) -> None:
    assert create(world)["show_as"] == "busy"
    assert create(world, show_as="free")["show_as"] == "free"


@pytest.mark.parametrize("value", ["out_of_office", "working_elsewhere", "tentative"])
def test_every_value_is_kept(world: World, value: str) -> None:
    event = create(world, show_as=value)
    assert world["api"]["owner"].get(f"/events/{event['id']}").json()["show_as"] == value
    assert [o["show_as"] for o in occurrences(world)] == [value]


def test_unknown_values_are_refused(world: World) -> None:
    res = world["api"]["owner"].post(
        f"/calendars/{world['cal']['id']}/events",
        {"title": "x", "start": iso(BASE), "end": iso(BASE + HOUR), "show_as": "away"},
    )
    assert res.status_code == 422


def test_an_edit_changes_it_and_one_without_it_keeps_it(world: World) -> None:
    event = create(world)
    api = world["api"]["owner"]
    assert api.patch(f"/events/{event['id']}", {"show_as": "out_of_office"}).json()["show_as"] == "out_of_office"
    assert api.patch(f"/events/{event['id']}", {"title": "Renamed"}).json()["show_as"] == "out_of_office"
    # PATCH: null is not "empty" here, it leaves the value as it is.
    assert api.patch(f"/events/{event['id']}", {"show_as": None}).json()["show_as"] == "out_of_office"


def test_the_activity_log_names_the_change(world: World) -> None:
    event = create(world)
    world["api"]["owner"].patch(f"/events/{event['id']}", {"show_as": "free"})
    updated = EventActivity.objects.get(event_id=event["id"], action="updated")
    assert updated.details == {"fields": ["show_as"]}


def test_changed_occurrences_start_with_the_series_value_and_can_differ(world: World) -> None:
    series = create(world, show_as="out_of_office", rrule="FREQ=DAILY;COUNT=3")
    api = world["api"]["owner"]
    second = iso(BASE + 24 * HOUR).replace("+", "%2B")
    changed = api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"title": "Moved"}).json()
    assert changed["show_as"] == "out_of_office"
    changed = api.patch(f"/events/{series['id']}/occurrences/{second}?scope=this", {"show_as": "free"}).json()
    assert changed["show_as"] == "free"
    assert [o["show_as"] for o in occurrences(world)] == ["out_of_office", "free", "out_of_office"]


def test_the_following_occurrences_keep_the_value_when_split_off(world: World) -> None:
    series = create(world, show_as="tentative", rrule="FREQ=DAILY;COUNT=3")
    second = iso(BASE + 24 * HOUR).replace("+", "%2B")
    following = (
        world["api"]["owner"]
        .patch(f"/events/{series['id']}/occurrences/{second}?scope=following", {"title": "Later"})
        .json()
    )
    assert following["id"] != series["id"]
    assert following["show_as"] == "tentative"


# ---------------------------------------------------------------------------
# iCalendar out
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "transp", "busystatus"),
    [
        ("busy", "OPAQUE", None),
        ("free", "TRANSPARENT", None),
        ("tentative", "OPAQUE", "TENTATIVE"),
        ("out_of_office", "OPAQUE", "OOF"),
        ("working_elsewhere", "TRANSPARENT", "WORKINGELSEWHERE"),
    ],
)
def test_written_as_transp_and_outlooks_busystatus(
    world: World, value: str, transp: str, busystatus: str | None
) -> None:
    event = Event.objects.get(id=create(world, show_as=value)["id"])
    text = lines(serialize_event_ical(event))
    assert [line for line in text if line.startswith("TRANSP")] == [f"TRANSP:{transp}"]
    expected = [f"X-MICROSOFT-CDO-BUSYSTATUS:{busystatus}"] if busystatus else []
    assert [line for line in text if line.startswith("X-MICROSOFT-CDO-BUSYSTATUS")] == expected


def test_the_feed_tells_subscribers_too(world: World) -> None:
    create(world, show_as="out_of_office")
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    FeedToken.objects.create(calendar=calendar, user=world["users"]["owner"], token="tok")
    body = lines(Client().get("/ics/tok.ics").content.decode())
    assert "TRANSP:OPAQUE" in body
    assert "X-MICROSOFT-CDO-BUSYSTATUS:OOF" in body


def test_a_value_set_in_the_app_replaces_what_a_client_stored(world: World) -> None:
    event = Event.objects.get(id=create(world)["id"])
    event.raw_ical = ics(event.uid, transp="TRANSPARENT", busystatus="FREE")
    event.save()
    world["api"]["owner"].patch(f"/events/{event.id}", {"show_as": "out_of_office"})
    event.refresh_from_db()
    text = lines(serialize_event_ical(event))
    assert [line for line in text if line.startswith(("TRANSP", "X-MICROSOFT"))] == [
        "TRANSP:OPAQUE",
        "X-MICROSOFT-CDO-BUSYSTATUS:OOF",
    ]


# ---------------------------------------------------------------------------
# CalDAV in
# ---------------------------------------------------------------------------


def ics(
    uid: str,
    start: datetime = BASE,
    transp: str | None = None,
    busystatus: str | None = None,
    override: str = "",
    rrule: str | None = None,
) -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    props = f"TRANSP:{transp}\r\n" if transp else ""
    props += f"X-MICROSOFT-CDO-BUSYSTATUS:{busystatus}\r\n" if busystatus else ""
    props += f"RRULE:{rrule}\r\n" if rrule else ""
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTAMP:{start.strftime(fmt)}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\nDTEND:{(start + HOUR).strftime(fmt)}\r\n"
        f"SUMMARY:From a client\r\n{props}"
        f"END:VEVENT\r\n{override}END:VCALENDAR\r\n"
    )


@pytest.fixture
def as_owner(world: World) -> Iterator[None]:
    with acting_as(world["users"]["owner"].email):
        yield


def upload(world: World, uid: str, text: str) -> Event:
    calendar = Calendar.objects.get(id=world["cal"]["id"])
    owner = world["users"]["owner"]
    coll = Collection(config.load(), f"/{owner.email}/{calendar.id}/", calendar=calendar, user=owner)
    coll.upload(f"{uid}.ics", radicale_item.Item(collection=coll, text=text))
    return Event.objects.get(calendar=calendar, uid=uid, parent__isnull=True)


@pytest.mark.usefixtures("as_owner")
@pytest.mark.parametrize(
    ("transp", "busystatus", "expected"),
    [
        # Thunderbird and Apple Calendar: TRANSP alone.
        (None, None, "busy"),
        ("OPAQUE", None, "busy"),
        ("TRANSPARENT", None, "free"),
        # Outlook (and the app's own output, sent back): both, agreeing.
        ("OPAQUE", "OOF", "out_of_office"),
        ("OPAQUE", "TENTATIVE", "tentative"),
        ("TRANSPARENT", "WORKINGELSEWHERE", "working_elsewhere"),
        ("TRANSPARENT", "FREE", "free"),
        # BUSYSTATUS alone, and in lower case.
        (None, "oof", "out_of_office"),
        # A client that only knows TRANSP changed it and sent the old BUSYSTATUS back: TRANSP wins.
        ("TRANSPARENT", "OOF", "free"),
        ("OPAQUE", "WORKINGELSEWHERE", "busy"),
        # Values nobody defined are read as what TRANSP says.
        ("OPAQUE", "SLEEPING", "busy"),
        ("SOMETIMES", None, "busy"),
    ],
)
def test_read_from_what_clients_send(world: World, transp: str | None, busystatus: str | None, expected: str) -> None:
    assert upload(world, "client-1", ics("client-1", transp=transp, busystatus=busystatus)).show_as == expected


@pytest.mark.usefixtures("as_owner")
def test_a_client_changing_transp_changes_the_event(world: World) -> None:
    event = upload(world, "client-2", ics("client-2", transp="OPAQUE", busystatus="OOF"))
    assert event.show_as == "out_of_office"
    # Thunderbird switches to "free" and keeps the property it doesn't know.
    event = upload(world, "client-2", ics("client-2", transp="TRANSPARENT", busystatus="OOF"))
    assert event.show_as == "free"
    activity = EventActivity.objects.filter(event=event, action="updated").get()
    assert activity.details == {"fields": ["show_as"]}
    # Served back, it says what the event is now, not what the client stored.
    text = lines(serialize_event_ical(event))
    assert [line for line in text if line.startswith(("TRANSP", "X-MICROSOFT"))] == ["TRANSP:TRANSPARENT"]


@pytest.mark.usefixtures("as_owner")
def test_a_changed_occurrence_has_its_own_value(world: World) -> None:
    fmt = "%Y%m%dT%H%M%SZ"
    second = BASE + 24 * HOUR
    override = (
        "BEGIN:VEVENT\r\nUID:client-3\r\n"
        f"DTSTAMP:{second.strftime(fmt)}\r\nRECURRENCE-ID:{second.strftime(fmt)}\r\n"
        f"DTSTART:{second.strftime(fmt)}\r\nDTEND:{(second + HOUR).strftime(fmt)}\r\n"
        "SUMMARY:Off that day\r\nTRANSP:TRANSPARENT\r\nEND:VEVENT\r\n"
    )
    series = upload(world, "client-3", ics("client-3", rrule="FREQ=DAILY;COUNT=3", override=override))
    assert series.show_as == "busy"
    assert [o.show_as for o in series.overrides.all()] == ["free"]
    assert [o["show_as"] for o in occurrences(world)] == ["busy", "free", "busy"]


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def availability(world: World, resources: tuple[str, ...] = ()) -> dict[str, Any]:
    data = {
        "start": iso(BASE - HOUR),
        "end": iso(BASE + 24 * HOUR),
        "user_ids": [world["users"]["booker"].id],
        "resource_ids": list(resources),
    }
    res = world["api"]["owner"].post("/availability", data)
    assert res.status_code == 200, res.content
    body: dict[str, Any] = res.json()
    return body


def periods(entry: dict[str, Any]) -> list[tuple[str, str, str]]:
    def kind(period: dict[str, Any]) -> str:
        return "away" if period["out_of_office"] else "maybe" if period["tentative"] else "busy"

    return [(p["start"][11:16], p["end"][11:16], kind(p)) for p in entry["busy"]]


@pytest.mark.parametrize("value", ["free", "working_elsewhere"])
def test_free_time_is_left_out_of_availability(world: World, value: str) -> None:
    create(world, "booker", show_as=value)
    assert periods(availability(world)["users"][0]) == []


def test_tentative_events_count_as_tentative(world: World) -> None:
    create(world, "booker", show_as="tentative")
    assert periods(availability(world)["users"][0]) == [("09:00", "10:00", "maybe")]


def test_out_of_office_is_told_apart(world: World) -> None:
    create(world, "booker", show_as="out_of_office", end=iso(BASE + 3 * HOUR))
    create(world, "booker", start=BASE + HOUR)  # busy within the time away: the time away shows
    create(world, "booker", start=BASE + 4 * HOUR)
    assert periods(availability(world)["users"][0]) == [("09:00", "12:00", "away"), ("13:00", "14:00", "busy")]


def test_busy_time_hides_tentative_time_within_it(world: World) -> None:
    create(world, "booker", end=iso(BASE + 2 * HOUR))
    create(world, "booker", show_as="tentative", start=BASE + HOUR)
    assert periods(availability(world)["users"][0]) == [("09:00", "11:00", "busy")]


def test_invitations_not_answered_yet_are_tentative_even_out_of_office(world: World) -> None:
    booker = world["users"]["booker"]
    invited = create(world, "owner", show_as="out_of_office", participants=[{"user_id": str(booker.id)}])
    assert periods(availability(world)["users"][0]) == [("09:00", "10:00", "maybe")]
    world["api"]["booker"].patch(f"/events/{invited['id']}/participants/me", {"status": "accepted"})
    assert periods(availability(world)["users"][0]) == [("09:00", "10:00", "away")]


def test_participants_follow_the_organizers_value(world: World) -> None:
    booker = world["users"]["booker"]
    invited = create(world, "owner", show_as="free", participants=[{"user_id": str(booker.id)}])
    world["api"]["booker"].patch(f"/events/{invited['id']}/participants/me", {"status": "accepted"})
    assert periods(availability(world)["users"][0]) == []


def test_resources_are_taken_whatever_the_event_shows(world: World) -> None:
    room = world["resource"]("Room", requires_approval=False)
    res = world["book"](world["api"]["booker"], room["id"], show_as="free")
    assert res.status_code == 200, res.content
    body = availability(world, resources=(room["id"],))
    assert periods(body["users"][0]) == []
    assert periods(body["resources"][0]) == [("09:00", "10:00", "busy")]
