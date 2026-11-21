"""
CalDAV driven through the mounted Radicale app, the way real clients talk to it.
"""

import base64
import io
import re
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict
from urllib.parse import unquote
from wsgiref.util import setup_testing_defaults
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.test.utils import CaptureQueriesContext
from icalendar.error import GloballyUniqueTZIDGuessed

from apps.core.caldav import auth
from apps.core.caldav.app import create_application
from apps.core.models import AppPassword, Calendar, CalendarMember, Event, FeedToken, User

# The CalDAV app tidies up the database connection after every request, which a test transaction can't survive.
pytestmark = pytest.mark.django_db(transaction=True)

PASSWORD = "secret-pw"

# Mounted under the CalDAV path, as config/asgi.py does.
PREFIX = "/caldav"
application = create_application()


def dav(
    method: str, path: str, user: User | str | None = None, body: str = "", password: str = PASSWORD, **headers: str
) -> tuple[int, str, dict[str, str]]:
    environ: dict[str, Any] = {}
    setup_testing_defaults(environ)
    data = body.encode()
    environ.update(
        REQUEST_METHOD=method,
        SCRIPT_NAME=PREFIX,
        PATH_INFO=path.removeprefix(PREFIX),
        CONTENT_LENGTH=str(len(data)),
        CONTENT_TYPE=headers.pop("content_type", "application/xml"),
    )
    environ["wsgi.input"] = io.BytesIO(data)
    if user is not None:
        login = user if isinstance(user, str) else user.email
        environ["HTTP_AUTHORIZATION"] = "Basic " + base64.b64encode(f"{login}:{password}".encode()).decode()
    for name, value in headers.items():
        environ["HTTP_" + name.upper()] = value
    response: dict[str, Any] = {}

    def start_response(
        status: str,
        response_headers: list[tuple[str, str]],
        exc_info: object = None,
    ) -> Callable[[bytes], object]:
        response["status"] = int(status.split()[0])
        response["headers"] = dict(response_headers)
        return lambda data: None  # the write() of old WSGI applications; Radicale doesn't use it

    content = b"".join(application(environ, start_response)).decode()
    return response["status"], content, response["headers"]


def hrefs(xml: str) -> list[str]:
    return [unquote(h) for h in re.findall(r"<href>([^<]*\.ics)</href>", xml)]


def ics(uid: str, start: str = "20301007T090000Z", end: str = "20301007T100000Z", summary: str = "Meeting") -> str:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:20300101T000000Z\r\n"
        f"DTSTART:{start}\r\nDTEND:{end}\r\nSUMMARY:{summary}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


def multiget(path: str, user: User, *item_paths: str) -> str:
    body = (
        '<?xml version="1.0"?><c:calendar-multiget xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
        + "".join(f"<d:href>{p}</d:href>" for p in item_paths)
        + "</c:calendar-multiget>"
    )
    status, content, _ = dav("REPORT", path, user, body, DEPTH="1")
    assert status == 207, content
    return content


def sync_collection(path: str, user: User, token: str = "") -> tuple[int, str]:
    body = (
        '<?xml version="1.0"?><d:sync-collection xmlns:d="DAV:">'
        f"<d:sync-token>{token}</d:sync-token><d:sync-level>1</d:sync-level>"
        "<d:prop><d:getetag/></d:prop></d:sync-collection>"
    )
    status, content, _ = dav("REPORT", path, user, body, DEPTH="1")
    return status, content


def sync_token(xml: str) -> str:
    match = re.search(r"<sync-token>([^<]*)</sync-token>", xml)
    assert match is not None
    return match.group(1)


class Team(TypedDict):
    users: dict[str, User]
    calendar: Calendar
    path: str


@pytest.fixture
def team() -> Team:
    users = {
        name: User.objects.create_user(email=f"{name}@example.test", password=PASSWORD, display_name=name.title())
        for name in ("owner", "own", "read", "outsider")
    }
    calendar = Calendar.objects.create(name="Team", owner=users["owner"])
    for name, role in (("owner", "owner"), ("own", "own"), ("read", "read")):
        CalendarMember.objects.create(calendar=calendar, user=users[name], role=role)
    FeedToken.objects.create(calendar=calendar, user=users["owner"], token="team-feed")
    path = f"/caldav/{users['owner'].email}/{calendar.id}/"
    return {"users": users, "calendar": calendar, "path": path}


def put(team: Team, href: str, user_name: str = "owner", text: str | None = None, **headers: str) -> int:
    status, content, _ = dav(
        "PUT",
        team["path"] + href,
        team["users"][user_name],
        text if text is not None else ics(href.removesuffix(".ics")),
        content_type="text/calendar",
        **headers,
    )
    return status


def test_multiget_returns_the_requested_events(team: Team) -> None:
    assert put(team, "one.ics") == 201
    assert put(team, "two.ics") == 201
    path = team["path"]
    content = multiget(path, team["users"]["owner"], path + "one.ics", path + "two.ics", path + "missing.ics")
    assert sorted(hrefs(content)) == sorted([path + "missing.ics", path + "one.ics", path + "two.ics"])
    assert "UID:one" in content and "UID:two" in content
    assert content.count("404 Not Found") == 1


def test_initial_sync_lists_every_event(team: Team) -> None:
    put(team, "one.ics")
    put(team, "two.ics")
    status, content = sync_collection(team["path"], team["users"]["owner"])
    assert status == 207
    assert sorted(hrefs(content)) == [team["path"] + "one.ics", team["path"] + "two.ics"]


def login(email: str, password: str) -> bool:
    from radicale.auth import AuthContext
    from radicale.config import load

    from apps.core.caldav.auth import Auth

    context = AuthContext()  # type: ignore[no-untyped-call]  # radicale leaves AuthContext.__init__ unannotated
    return Auth(load())._login_ext(email, password, context) == email


def test_deactivated_users_cannot_log_in(team: Team) -> None:
    user = team["users"]["read"]
    assert login(user.email, PASSWORD)
    user.is_active = False
    user.save()
    assert not login(user.email, PASSWORD)


def test_app_passwords_replace_the_account_password(team: Team) -> None:
    user = team["users"]["read"]
    AppPassword.objects.create(user=user, label="Phone", password_hash=make_password("app-pw"))
    assert login(user.email, "app-pw")
    assert not login(user.email, PASSWORD)
    assert AppPassword.objects.get(user=user).last_used_at is not None


def test_requests_are_answered_for_valid_credentials_only(team: Team) -> None:
    owner = team["users"]["owner"]
    assert dav("PROPFIND", team["path"], owner, DEPTH="0")[0] == 207
    assert dav("PROPFIND", team["path"], owner, password="wrong", DEPTH="0")[0] == 401


def test_contributors_change_only_their_own_events(team: Team) -> None:
    assert put(team, "by-owner.ics") == 201
    assert put(team, "by-owner.ics", "own", ics("by-owner", summary="Hijacked")) == 403
    assert dav("DELETE", team["path"] + "by-owner.ics", team["users"]["own"])[0] == 403
    assert Event.objects.get(uid="by-owner").title == "Meeting"

    assert put(team, "mine.ics", "own") == 201
    mine = Event.objects.get(uid="mine")
    assert mine.creator == team["users"]["own"]
    assert put(team, "mine.ics", "own", ics("mine", summary="Renamed")) == 204
    assert dav("DELETE", team["path"] + "mine.ics", team["users"]["own"])[0] == 200
    assert not Event.objects.filter(uid="mine").exists()


def test_editors_change_everyones_events(team: Team) -> None:
    put(team, "mine.ics", "own")
    team["calendar"].members.filter(user=team["users"]["own"]).update(role="full")
    put(team, "by-owner.ics")
    assert put(team, "by-owner.ics", "own", ics("by-owner", summary="Edited")) == 204
    assert dav("DELETE", team["path"] + "by-owner.ics", team["users"]["own"])[0] == 200


def test_viewers_and_outsiders_cannot_write(team: Team) -> None:
    put(team, "by-owner.ics")
    for name in ("read", "outsider"):
        assert put(team, "new.ics", name) == 403
        assert dav("DELETE", team["path"] + "by-owner.ics", team["users"][name])[0] in (403, 404)
    assert Event.objects.filter(uid="by-owner").exists()
    assert not Event.objects.filter(uid="new").exists()


def test_only_the_owner_renames_the_calendar(team: Team) -> None:
    body = (
        '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:"><d:set><d:prop>'
        "<d:displayname>Renamed</d:displayname></d:prop></d:set></d:propertyupdate>"
    )
    assert dav("PROPPATCH", team["path"], team["users"]["own"], body)[0] == 403
    assert Calendar.objects.get(id=team["calendar"].id).name == "Team"
    assert dav("PROPPATCH", team["path"], team["users"]["owner"], body)[0] == 207
    assert Calendar.objects.get(id=team["calendar"].id).name == "Renamed"


@pytest.mark.parametrize("method", ["GET", "PROPFIND"])
@pytest.mark.parametrize("path", ["/.well-known/caldav", "/.well-known/caldav/"])
def test_well_known_caldav_redirects_to_the_caldav_root(team: Team, method: str, path: str) -> None:
    status, _, headers = dav(method, path, team["users"]["owner"])
    assert status == 301
    assert headers["Location"] == "/caldav/"


def test_events_stay_at_the_href_the_client_chose(team: Team) -> None:
    path = team["path"]
    assert put(team, "client-name.ics", text=ics("another-uid")) == 201
    status, content, _ = dav("GET", path + "client-name.ics", team["users"]["owner"])
    assert status == 200 and "UID:another-uid" in content
    assert dav("GET", path + "another-uid.ics", team["users"]["owner"])[0] == 404

    content = multiget(path, team["users"]["owner"], path + "client-name.ics")
    assert hrefs(content) == [path + "client-name.ics"] and "UID:another-uid" in content

    assert put(team, "client-name.ics", text=ics("another-uid", summary="Renamed")) == 204
    assert Event.objects.get(uid="another-uid").title == "Renamed"
    # The same UID can't be stored twice under different names.
    assert put(team, "second-name.ics", text=ics("another-uid")) == 409

    assert dav("DELETE", path + "client-name.ics", team["users"]["owner"])[0] == 200
    assert not Event.objects.filter(uid="another-uid").exists()


def test_events_from_the_app_are_found_by_uid(team: Team) -> None:
    owner = team["users"]["owner"]
    Event.objects.create(
        calendar=team["calendar"],
        creator=owner,
        title="From the app",
        uid="app-event",
        start=datetime(2030, 10, 7, 9, tzinfo=UTC),
        end=datetime(2030, 10, 7, 10, tzinfo=UTC),
    )
    status, content, _ = dav("GET", team["path"] + "app-event.ics", owner)
    assert status == 200 and "SUMMARY:From the app" in content
    assert put(team, "app-event.ics", text=ics("app-event", summary="Edited on the phone")) == 204
    assert Event.objects.get(uid="app-event").title == "Edited on the phone"


def changes(xml: str) -> dict[str, str]:
    """href -> "found" or "deleted" from a sync-collection answer."""
    result = {}
    for response in re.findall(r"<response>(.*?)</response>", xml, re.S):
        match = re.search(r"<href>([^<]*)</href>", response)
        assert match is not None
        href = unquote(match.group(1))
        result[href.rsplit("/", 1)[1]] = "deleted" if "404 Not Found" in response else "found"
    return result


def test_sync_reports_changes_and_deletions(team: Team) -> None:
    owner, path = team["users"]["owner"], team["path"]
    for name in ("keep", "edit", "drop"):
        put(team, f"{name}.ics")
    # Changes from the last half minute are reported again in case they committed late.
    Event.objects.update(updated_at=datetime.now(UTC) - timedelta(minutes=5))
    _, content = sync_collection(path, owner)
    token = sync_token(content)

    _, content = sync_collection(path, owner, token)
    assert changes(content) == {} and sync_token(content) == token

    put(team, "edit.ics", text=ics("edit", summary="Edited"))
    dav("DELETE", path + "drop.ics", owner)
    put(team, "new.ics")
    _, content = sync_collection(path, owner, token)
    assert changes(content) == {"edit.ics": "found", "drop.ics": "deleted", "new.ics": "found"}
    assert sync_token(content) != token


def test_sync_reports_events_deleted_in_the_app(team: Team) -> None:
    owner, path = team["users"]["owner"], team["path"]
    put(team, "drop.ics")
    token = sync_token(sync_collection(path, owner)[1])
    Event.objects.get(uid="drop").delete()
    assert changes(sync_collection(path, owner, token)[1]) == {"drop.ics": "deleted"}


def test_sync_drops_bookings_that_turn_hidden(team: Team) -> None:
    owner, path = team["users"]["owner"], team["path"]
    put(team, "booking.ics")
    token = sync_token(sync_collection(path, owner)[1])
    event = Event.objects.get(uid="booking")
    event.status = "cancelled"
    event.save()
    assert changes(sync_collection(path, owner, token)[1]) == {"booking.ics": "deleted"}


@pytest.mark.parametrize(
    "token", ["garbage", "http://radicale.org/ns/sync/0123abc", "http://radicale.org/ns/sync/1000-x"]
)
def test_unknown_or_expired_sync_tokens_ask_for_a_full_sync(team: Team, token: str) -> None:
    status, content = sync_collection(team["path"], team["users"]["owner"], token)
    assert status == 403 and "valid-sync-token" in content


def test_ctag_changes_when_an_event_is_deleted(team: Team) -> None:
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/"><d:prop><cs:getctag/></d:prop></d:propfind>'

    def ctag() -> str:
        match = re.search(
            r"getctag>([^<]*)<", dav("PROPFIND", team["path"], team["users"]["owner"], body, DEPTH="0")[1]
        )
        assert match is not None
        return match.group(1)

    put(team, "one.ics")
    put(team, "two.ics")
    before = ctag()
    assert ctag() == before
    dav("DELETE", team["path"] + "two.ics", team["users"]["owner"])
    assert ctag() != before


def series_ics(uid: str, *, master_last: bool = False, with_override: bool = True) -> str:
    master = (
        f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:20300101T000000Z\r\n"
        "DTSTART;TZID=Europe/Berlin:20301007T090000\r\nDTEND;TZID=Europe/Berlin:20301007T100000\r\n"
        "RRULE:FREQ=DAILY;COUNT=5\r\nEXDATE;TZID=Europe/Berlin:20301008T090000\r\n"
        "SUMMARY:Daily\r\nEND:VEVENT\r\n"
    )
    override = (
        (
            f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:20300101T000000Z\r\n"
            "RECURRENCE-ID;TZID=Europe/Berlin:20301009T090000\r\n"
            "DTSTART;TZID=Europe/Berlin:20301009T140000\r\nDTEND;TZID=Europe/Berlin:20301009T150000\r\n"
            "SUMMARY:Daily (moved)\r\nEND:VEVENT\r\n"
        )
        if with_override
        else ""
    )
    body = override + master if master_last else master + override
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n{body}END:VCALENDAR\r\n"


def occurrences_in_app(
    team: Team, start: str = "2030-10-01T00:00:00Z", end: str = "2030-11-01T00:00:00Z"
) -> list[tuple[str, str]]:
    from django.test import Client

    client = Client()
    client.force_login(team["users"]["owner"])
    response = client.get("/api/events", {"start": start, "end": end, "calendar_ids": str(team["calendar"].id)})
    assert response.status_code == 200, response.content
    return [(o["start"], o["title"]) for o in response.json()]


@pytest.mark.parametrize("master_last", [False, True])
def test_series_with_exceptions_round_trip(team: Team, master_last: bool) -> None:
    assert put(team, "daily.ics", text=series_ics("daily", master_last=master_last)) == 201
    series = Event.objects.get(uid="daily", parent__isnull=True)
    assert series.rrule == "FREQ=DAILY;COUNT=5"
    assert series.exdates == ["2030-10-08T07:00:00+00:00"]
    override = series.overrides.get()
    assert override.recurrence_id == datetime(2030, 10, 9, 7, tzinfo=UTC)
    assert override.title == "Daily (moved)"

    assert occurrences_in_app(team) == [
        ("2030-10-07T07:00:00Z", "Daily"),
        ("2030-10-09T12:00:00Z", "Daily (moved)"),
        ("2030-10-10T07:00:00Z", "Daily"),
        ("2030-10-11T07:00:00Z", "Daily"),
    ]

    status, content, _ = dav("GET", team["path"] + "daily.ics", team["users"]["owner"])
    assert status == 200
    assert content.count("BEGIN:VEVENT") == 2
    assert "EXDATE;TZID=Europe/Berlin:20301008T090000" in content
    assert "RECURRENCE-ID;TZID=Europe/Berlin:20301009T090000" in content

    # Leaving the change out restores the occurrence.
    assert put(team, "daily.ics", text=series_ics("daily", with_override=False)) == 204
    assert not series.overrides.exists()
    assert ("2030-10-09T07:00:00Z", "Daily") in occurrences_in_app(team)


def test_all_day_events_keep_their_length(team: Team) -> None:
    text = (
        ics("allday")
        .replace("DTSTART:20301007T090000Z", "DTSTART;VALUE=DATE:20301007")
        .replace("DTEND:20301007T100000Z", "DTEND;VALUE=DATE:20301008")
    )
    assert put(team, "allday.ics", text=text) == 201
    event = Event.objects.get(uid="allday")
    assert event.all_day and event.start == event.end == datetime(2030, 10, 7, tzinfo=UTC)
    content = dav("GET", team["path"] + "allday.ics", team["users"]["owner"])[1]
    assert "DTSTART;VALUE=DATE:20301007" in content and "DTEND;VALUE=DATE:20301008" in content


def test_duration_sets_the_end(team: Team) -> None:
    text = ics("dur").replace("DTEND:20301007T100000Z", "DURATION:PT2H30M")
    assert put(team, "dur.ics", text=text) == 201
    assert Event.objects.get(uid="dur").end == datetime(2030, 10, 7, 11, 30, tzinfo=UTC)
    content = dav("GET", team["path"] + "dur.ics", team["users"]["owner"])[1]
    assert "DURATION" not in content and "DTEND:20301007T113000Z" in content


def test_tasks_are_refused(team: Team) -> None:
    todo = ics("task").replace("VEVENT", "VTODO")
    assert put(team, "task.ics", text=todo) in (400, 403, 415)
    assert not Event.objects.filter(uid="task").exists()


def test_all_day_series_until_a_date(team: Team) -> None:
    text = (
        ics("weekly")
        .replace("DTSTART:20301007T090000Z", "DTSTART;VALUE=DATE:20301007")
        .replace("DTEND:20301007T100000Z", "DTEND;VALUE=DATE:20301008\r\nRRULE:FREQ=WEEKLY;UNTIL=20301021")
    )
    assert put(team, "weekly.ics", text=text) == 201
    assert [s for s, _ in occurrences_in_app(team)] == [
        "2030-10-07T00:00:00Z",
        "2030-10-14T00:00:00Z",
        "2030-10-21T00:00:00Z",
    ]
    content = dav("GET", team["path"] + "weekly.ics", team["users"]["owner"])[1]
    assert "UNTIL=20301021" in content and "UNTIL=20301021T" not in content


def test_caldav_shows_the_current_booking_status(team: Team) -> None:
    from apps.core.services.ical import serialize_event_ical

    owner = team["users"]["owner"]
    event = Event.objects.create(
        calendar=team["calendar"],
        creator=owner,
        title="Room",
        uid="booking",
        status="pending",
        start=datetime(2030, 10, 7, 9, tzinfo=UTC),
        end=datetime(2030, 10, 7, 10, tzinfo=UTC),
    )
    event.raw_ical = serialize_event_ical(event)
    event.save()
    event.status = "approved"
    event.save()
    content = dav("GET", team["path"] + "booking.ics", owner)[1]
    assert "STATUS:CONFIRMED" in content and "TENTATIVE" not in content


def test_shared_calendars_are_listed_in_every_members_home(team: Team) -> None:
    contributor = team["users"]["own"]
    home = f"/caldav/{contributor.email}/"
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>'
    status, content, _ = dav("PROPFIND", home, contributor, body, DEPTH="1")
    assert status == 207
    assert f"{team['calendar'].id}/" in content and "<displayname>Team</displayname>" in content

    own_path = f"{home}{team['calendar'].id}/"
    assert put(team, "x.ics", "own") == 201
    status, content, _ = dav("GET", own_path + "x.ics", contributor)
    assert status == 200 and "UID:x" in content
    # The owner's path keeps working for clients set up with it.
    assert dav("GET", team["path"] + "x.ics", contributor)[0] == 200

    outsider = team["users"]["outsider"]
    assert dav("PROPFIND", f"/caldav/{outsider.email}/{team['calendar'].id}/", outsider, DEPTH="0")[0] in (403, 404)
    # Nobody reaches a calendar through someone else's home.
    assert dav("GET", own_path + "x.ics", team["users"]["read"])[0] in (403, 404)


def test_occurrences_changed_in_the_app_reach_clients(team: Team) -> None:
    from django.test import Client

    owner, path = team["users"]["owner"], team["path"]
    put(team, "daily.ics", text=series_ics("daily", with_override=False))
    Event.objects.update(updated_at=datetime.now(UTC) - timedelta(minutes=5))
    token = sync_token(sync_collection(path, owner)[1])

    client = Client()
    client.force_login(owner)
    series = Event.objects.get(uid="daily")
    response = client.patch(
        f"/api/events/{series.id}/occurrences/2030-10-10T07:00:00Z?scope=this",
        {"title": "Changed in the app"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content

    assert changes(sync_collection(path, owner, token)[1]) == {"daily.ics": "found"}
    content = dav("GET", path + "daily.ics", owner)[1]
    assert "RECURRENCE-ID;TZID=Europe/Berlin:20301010T090000" in content
    assert "SUMMARY:Changed in the app" in content
    # The client's own series keeps its removed occurrence.
    assert "EXDATE;TZID=Europe/Berlin:20301008T090000" in content


def move(team: Team, from_path: str, to_path: str, user_name: str = "owner", **headers: str) -> int:
    return dav("MOVE", from_path, team["users"][user_name], DESTINATION=to_path, **headers)[0]


@pytest.fixture
def other_calendar(team: Team) -> tuple[Calendar, str]:
    calendar = Calendar.objects.create(name="Other", owner=team["users"]["owner"])
    CalendarMember.objects.create(calendar=calendar, user=team["users"]["owner"], role="owner")
    return calendar, f"/caldav/{team['users']['owner'].email}/{calendar.id}/"


def test_move_renames_an_event(team: Team) -> None:
    owner, path = team["users"]["owner"], team["path"]
    put(team, "old.ics")
    Event.objects.update(updated_at=datetime.now(UTC) - timedelta(minutes=5))
    token = sync_token(sync_collection(path, owner)[1])

    assert move(team, path + "old.ics", path + "new.ics") == 201
    assert dav("GET", path + "new.ics", owner)[0] == 200
    assert dav("GET", path + "old.ics", owner)[0] == 404
    assert changes(sync_collection(path, owner, token)[1]) == {"old.ics": "deleted", "new.ics": "found"}


def test_move_to_another_calendar(team: Team, other_calendar: tuple[Calendar, str]) -> None:
    calendar, other_path = other_calendar
    owner, path = team["users"]["owner"], team["path"]
    put(team, "event.ics")
    token = sync_token(sync_collection(path, owner)[1])

    assert move(team, path + "event.ics", other_path + "event.ics") == 201
    assert Event.objects.get(uid="event").calendar_id == calendar.id
    assert dav("GET", other_path + "event.ics", owner)[0] == 200
    assert changes(sync_collection(path, owner, token)[1]) == {"event.ics": "deleted"}


def test_move_needs_write_access_on_both_sides(team: Team, other_calendar: tuple[Calendar, str]) -> None:
    calendar, other_path = other_calendar
    CalendarMember.objects.create(calendar=calendar, user=team["users"]["own"], role="read")
    put(team, "mine.ics", "own")
    put(team, "theirs.ics")
    # Viewer in the target calendar.
    assert move(team, team["path"] + "mine.ics", other_path + "mine.ics", "own") == 403
    # Someone else's event in the source calendar.
    CalendarMember.objects.filter(calendar=calendar, user=team["users"]["own"]).update(role="own")
    assert move(team, team["path"] + "theirs.ics", other_path + "theirs.ics", "own") == 403
    assert move(team, team["path"] + "mine.ics", other_path + "mine.ics", "own") == 201


def test_bookings_stay_in_their_calendar(team: Team, other_calendar: tuple[Calendar, str]) -> None:
    from apps.core.models import Resource

    _, other_path = other_calendar
    put(team, "booking.ics")
    room = Resource.objects.create(calendar=team["calendar"], name="Room")
    Event.objects.filter(uid="booking").update(resource=room)
    assert move(team, team["path"] + "booking.ics", other_path + "booking.ics") == 403
    assert Event.objects.get(uid="booking").calendar_id == team["calendar"].id


def test_move_overwrites_only_when_asked(team: Team) -> None:
    path = team["path"]
    put(team, "a.ics")
    put(team, "b.ics")
    assert move(team, path + "a.ics", path + "b.ics") == 412
    # The target holds another UID, which Radicale refuses to overwrite.
    assert move(team, path + "a.ics", path + "b.ics", OVERWRITE="T") == 409
    assert Event.objects.filter(uid__in=["a", "b"]).count() == 2


def mkcalendar(user: User, path: str, components: str = "VEVENT", name: str = "Phone calendar") -> int:
    body = (
        '<?xml version="1.0"?><c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:set><d:prop>'
        f"<d:displayname>{name}</d:displayname>"
        f'<c:supported-calendar-component-set><c:comp name="{components}"/></c:supported-calendar-component-set>'
        "</d:prop></d:set></c:mkcalendar>"
    )
    return dav("MKCALENDAR", path, user, body)[0]


def test_clients_create_calendars_in_their_home(team: Team) -> None:
    contributor = team["users"]["own"]
    path = f"/caldav/{contributor.email}/3F2504E0-4F89-11D3-9A0C-0305E82C3301/"
    assert mkcalendar(contributor, path) == 201
    calendar = Calendar.objects.get(dav_name="3F2504E0-4F89-11D3-9A0C-0305E82C3301")
    assert calendar.name == "Phone calendar" and calendar.owner == contributor
    assert calendar.members.get().role == "owner"

    # The client keeps using the address it chose.
    status, content, _ = dav("PUT", path + "e.ics", contributor, ics("e"), content_type="text/calendar")
    assert status == 201
    assert Event.objects.get(uid="e").calendar == calendar
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>'
    content = dav("PROPFIND", f"/caldav/{contributor.email}/", contributor, body, DEPTH="1")[1]
    assert "3F2504E0-4F89-11D3-9A0C-0305E82C3301/" in content
    # The app's address keeps working, too.
    assert dav("GET", f"/caldav/{contributor.email}/{calendar.id}/e.ics", contributor)[0] == 200


def test_calendars_are_not_created_elsewhere_or_for_tasks(team: Team) -> None:
    contributor, owner = team["users"]["own"], team["users"]["owner"]
    assert mkcalendar(contributor, f"/caldav/{owner.email}/new/") == 403
    assert mkcalendar(contributor, f"/caldav/{contributor.email}/tasks/", components="VTODO") == 403
    assert mkcalendar(contributor, f"/caldav/{contributor.email}/{team['calendar'].id}/") in (403, 405, 409)
    assert Calendar.objects.count() == 1
    # Nor under another calendar's id, which names that calendar in every path.
    outsider = team["users"]["outsider"]
    assert mkcalendar(outsider, f"/caldav/{outsider.email}/{team['calendar'].id}/") in (403, 405, 409)
    assert Calendar.objects.count() == 1


def test_only_the_owner_deletes_a_calendar(team: Team) -> None:
    calendar = team["calendar"]
    put(team, "e.ics")
    assert dav("DELETE", team["path"], team["users"]["own"])[0] == 403
    assert Calendar.objects.filter(id=calendar.id).exists()
    assert dav("DELETE", team["path"], team["users"]["owner"])[0] == 200
    assert not Calendar.objects.filter(id=calendar.id).exists()
    assert not Event.objects.filter(uid="e").exists()


def vevent_ics(uid: str, lines: str) -> str:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:20300101T000000Z\r\n{lines}END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


def test_long_titles_are_cut(team: Team) -> None:
    assert put(team, "long.ics", text=ics("long", summary="x" * 400)) == 201
    assert len(Event.objects.get(uid="long").title) == 255


def test_all_day_calendars_refuse_timed_events(team: Team) -> None:
    Calendar.objects.filter(id=team["calendar"].id).update(force_all_day=True)
    assert put(team, "timed.ics") == 403
    text = (
        ics("day")
        .replace("DTSTART:20301007T090000Z", "DTSTART;VALUE=DATE:20301007")
        .replace("DTEND:20301007T100000Z", "DTEND;VALUE=DATE:20301008")
    )
    assert put(team, "day.ics", text=text) == 201


def test_changes_from_clients_are_recorded(team: Team) -> None:
    from apps.core.models import EventActivity

    put(team, "daily.ics", "own", series_ics("daily", with_override=False))
    put(team, "daily.ics", "own", series_ics("daily").replace("SUMMARY:Daily\r\n", "SUMMARY:Standup\r\n"))
    series = Event.objects.get(uid="daily", parent__isnull=True)
    entries = [
        (a.action, a.actor.email if a.actor else None, a.details)
        for a in EventActivity.objects.filter(event=series).order_by("created_at")
    ]
    assert entries[0] == ("created", "own@example.test", None)
    assert entries[1] == ("updated", "own@example.test", {"fields": ["title"]})
    assert ("occurrence_changed", "own@example.test", {"occurrence": "2030-10-09T07:00:00+00:00"}) in entries


def test_owner_sets_the_calendar_color(team: Team) -> None:
    body = (
        '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:i="http://apple.com/ns/ical/"><d:set><d:prop>'
        "<i:calendar-color>#FF2968FF</i:calendar-color></d:prop></d:set></d:propertyupdate>"
    )
    assert dav("PROPPATCH", team["path"], team["users"]["owner"], body)[0] == 207
    calendar = Calendar.objects.get(id=team["calendar"].id)
    assert calendar.event_color == calendar.dark_event_color == "#ff2968"


def test_floating_times_are_read_in_the_writers_zone(team: Team) -> None:
    User.objects.filter(email="owner@example.test").update(timezone="Europe/Berlin")
    text = vevent_ics("float", "DTSTART:20300701T090000\r\nDTEND:20300701T100000\r\nSUMMARY:Floating\r\n")
    assert put(team, "float.ics", text=text) == 201
    event = Event.objects.get(uid="float")
    assert event.start == datetime(2030, 7, 1, 7, tzinfo=UTC)
    assert event.timezone == "Europe/Berlin"


@pytest.mark.parametrize(
    ("tzid", "guessed"),
    [
        ("W. Europe Standard Time", False),
        # A vendor-prefixed TZID (older Mozilla clients): icalendar warns that it guesses the zone.
        ("/mozilla.org/20070129_1/Europe/Berlin", True),
    ],
)
def test_zones_by_other_names(team: Team, tzid: str, guessed: bool) -> None:
    text = vevent_ics(
        "weekly",
        f"DTSTART;TZID={tzid}:20300107T090000\r\nDTEND;TZID={tzid}:20300107T100000\r\nRRULE:FREQ=WEEKLY;COUNT=30\r\nSUMMARY:Weekly\r\n",
    )
    with pytest.warns(GloballyUniqueTZIDGuessed) if guessed else nullcontext():
        assert put(team, "weekly.ics", text=text) == 201
    event = Event.objects.get(uid="weekly")
    assert event.timezone == "Europe/Berlin"
    starts = [s for s, _ in occurrences_in_app(team, "2030-01-01T00:00:00Z", "2030-08-01T00:00:00Z")]
    # 09:00 in Berlin, in winter and in summer.
    assert starts[0] == "2030-01-07T08:00:00Z" and "2030-07-01T07:00:00Z" in starts


def test_extra_dates_of_a_series(team: Team) -> None:
    text = vevent_ics(
        "extra",
        "DTSTART:20301007T090000Z\r\nDTEND:20301007T100000Z\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
        "RDATE:20301009T090000Z,20301020T090000Z\r\nSUMMARY:Extra\r\n",
    )
    assert put(team, "extra.ics", text=text) == 201
    assert [s for s, _ in occurrences_in_app(team)] == [
        "2030-10-07T09:00:00Z",
        "2030-10-09T09:00:00Z",
        "2030-10-14T09:00:00Z",
        "2030-10-20T09:00:00Z",
    ]
    content = dav("GET", team["path"] + "extra.ics", team["users"]["owner"])[1]
    assert "RDATE:20301009T090000Z" in content and "RDATE:20301020T090000Z" in content


def test_category_resource_and_participants(team: Team) -> None:
    from apps.core.models import Category, EventParticipant, Resource

    Category.objects.create(calendar=team["calendar"], name="Workshop", color="#ff0000")
    projector = Resource.objects.create(calendar=team["calendar"], name="Projector")
    text = vevent_ics(
        "meet",
        "DTSTART:20301007T090000Z\r\nDTEND:20301007T100000Z\r\nSUMMARY:Meet\r\n"
        "CATEGORIES:workshop,Private\r\n"
        "ORGANIZER;CN=Owner:mailto:owner@example.test\r\n"
        "ATTENDEE;PARTSTAT=ACCEPTED:mailto:owner@example.test\r\n"
        "ATTENDEE;PARTSTAT=TENTATIVE:mailto:Read@example.test\r\n"
        "ATTENDEE:mailto:guest@elsewhere.test\r\n",
    )
    assert put(team, "meet.ics", text=text) == 201
    event = Event.objects.get(uid="meet")
    assert event.category is not None and event.category.name == "Workshop"
    assert {(p.email, p.status, bool(p.user)) for p in EventParticipant.objects.filter(event=event)} == {
        ("read@example.test", "tentative", True),
        ("guest@elsewhere.test", "needs_action", False),
    }
    Event.objects.filter(pk=event.pk).update(resource=projector)

    # Long lines are folded (RFC 5545); unfolded for the checks.
    content = dav("GET", team["path"] + "meet.ics", team["users"]["owner"])[1].replace("\r\n ", "")
    assert "CATEGORIES:Workshop,Private" in content
    # The booked resource is a resource, not the location.
    assert "RESOURCES:Projector" in content and "LOCATION" not in content
    assert "ORGANIZER;CN=Owner:mailto:owner@example.test" in content
    assert "PARTSTAT=TENTATIVE" in content and "mailto:guest@elsewhere.test" in content

    feed = __import__("django.test", fromlist=["Client"]).Client().get("/ics/team-feed.ics").content.decode()
    assert "CATEGORIES:Workshop,Private" in feed and "RESOURCES:Projector" in feed
    assert "ATTENDEE" not in feed and "ORGANIZER" not in feed and "mailto:" not in feed

    # Dropping an attendee on the phone removes the participant.
    assert put(team, "meet.ics", text=text.replace("ATTENDEE:mailto:guest@elsewhere.test\r\n", "")) == 204
    assert list(EventParticipant.objects.filter(event=event).values_list("email", flat=True)) == ["read@example.test"]


def test_reminders_are_per_user(team: Team) -> None:
    from apps.core.models import EventReminder

    text = vevent_ics(
        "remind",
        "DTSTART:20301007T090000Z\r\nDTEND:20301007T100000Z\r\nSUMMARY:Remind\r\n"
        "BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:x\r\nTRIGGER:-PT15M\r\nEND:VALARM\r\n"
        "BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:x\r\nTRIGGER;VALUE=DATE-TIME:20301006T090000Z\r\nEND:VALARM\r\n",
    )
    assert put(team, "remind.ics", text=text) == 201
    event = Event.objects.get(uid="remind")
    assert sorted(
        EventReminder.objects.filter(event=event, user=team["users"]["owner"]).values_list("minutes_before", flat=True)
    ) == [15, 1440]

    owner_view = dav("GET", team["path"] + "remind.ics", team["users"]["owner"])[1]
    assert owner_view.count("BEGIN:VALARM") == 2 and "TRIGGER:-PT15M" in owner_view
    assert "BEGIN:VALARM" not in dav("GET", team["path"] + "remind.ics", team["users"]["read"])[1]
    assert (
        "BEGIN:VALARM"
        not in __import__("django.test", fromlist=["Client"]).Client().get("/ics/team-feed.ics").content.decode()
    )


def test_location_and_booked_place(team: Team) -> None:
    from apps.core.models import Resource

    text = vevent_ics(
        "loc", "DTSTART:20301007T090000Z\r\nDTEND:20301007T100000Z\r\nSUMMARY:Loc\r\nLOCATION:Café Central\r\n"
    )
    assert put(team, "loc.ics", text=text) == 201
    event = Event.objects.get(uid="loc")
    assert event.location == "Café Central" and event.location_resource is None

    room = Resource.objects.create(calendar=team["calendar"], name="Room 1", is_location=True)
    Event.objects.filter(pk=event.pk).update(location_resource=room, location="Room 1")
    content = dav("GET", team["path"] + "loc.ics", team["users"]["owner"])[1]
    assert "LOCATION:Room 1" in content and "RESOURCES" not in content
    # A booked place is changed in the app only: the client's other location doesn't replace it.
    assert put(team, "loc.ics", text=text) == 204
    event.refresh_from_db()
    assert (event.location, event.location_resource_id) == ("Room 1", room.id)


# --- Cost ----------------------------------------------------------------------------------------
# A request costs the same however many events a calendar has, and a password is checked once.

COST_START = datetime(2030, 1, 7, 9, tzinfo=UTC)


def add_events(team: Team, numbers: range) -> None:
    for i in numbers:
        start = COST_START + timedelta(hours=i)
        Event.objects.create(
            calendar=team["calendar"],
            creator=team["users"]["owner"],
            uid=f"event-{i}",
            title=f"E{i}",
            start=start,
            end=start + timedelta(minutes=30),
        )


def propfind_queries(team: Team) -> int:
    with CaptureQueriesContext(connection) as queries:
        status, _, _ = dav("PROPFIND", team["path"], team["users"]["owner"], DEPTH="1")
    assert status == 207
    return len(queries)


def test_listing_a_calendar_costs_the_same_for_more_events(team: Team) -> None:
    add_events(team, range(5))
    few = propfind_queries(team)
    add_events(team, range(5, 55))
    assert propfind_queries(team) == few


def test_a_password_is_checked_once_and_a_deleted_app_password_stops_working(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = team["users"]["owner"]
    app_password = AppPassword.objects.create(user=user, label="Phone", password_hash=make_password("app-pw"))
    checks: list[str] = []

    def counted_check(password: str, encoded: str) -> bool:
        checks.append(password)
        return check_password(password, encoded)

    monkeypatch.setattr(auth, "check_password", counted_check)

    for _ in range(3):
        assert dav("PROPFIND", team["path"], user, password="app-pw", DEPTH="0")[0] == 207
    assert len(checks) == 1
    assert dav("PROPFIND", team["path"], user, password="wrong", DEPTH="0")[0] == 401

    app_password.delete()
    assert dav("PROPFIND", team["path"], user, password="app-pw", DEPTH="0")[0] == 401


def test_failed_logins_are_limited_like_the_web_login(team: Team) -> None:
    user, path = team["users"]["owner"], team["path"]
    for _ in range(auth.MAX_FAILED_LOGINS):
        assert dav("PROPFIND", path, user, password="guess", DEPTH="0")[0] == 401
    # Now even the right password is refused for a while; other logins are not affected.
    assert dav("PROPFIND", path, user, DEPTH="0")[0] == 401
    assert dav("PROPFIND", f"/caldav/{team['users']['own'].email}/", team["users"]["own"], DEPTH="0")[0] == 207


def test_the_feed_leaves_out_what_clients_note_for_members(team: Team) -> None:
    owner = team["users"]["owner"]
    body = ics("notes").replace(
        "SUMMARY:Meeting\r\n",
        "SUMMARY:Meeting\r\nCOMMENT:Call Ann on 0123\r\nX-PRIVATE-NOTE:ask about salary\r\nTRANSP:OPAQUE\r\n",
    )
    assert dav("PUT", team["path"] + "notes.ics", owner, body, content_type="text/calendar")[0] == 201
    members = dav("GET", team["path"] + "notes.ics", owner)[1]
    assert "COMMENT:Call Ann" in members and "X-PRIVATE-NOTE" in members

    feed = __import__("django.test", fromlist=["Client"]).Client().get("/ics/team-feed.ics").content.decode()
    assert "SUMMARY:Meeting" in feed and "TRANSP:OPAQUE" in feed
    assert "Call Ann" not in feed and "X-PRIVATE-NOTE" not in feed


def test_expanded_queries_with_etags_work_for_series(team: Team) -> None:
    owner = team["users"]["owner"]
    body = ics("series").replace("SUMMARY:Meeting\r\n", "SUMMARY:Meeting\r\nRRULE:FREQ=DAILY;COUNT=3\r\n")
    assert dav("PUT", team["path"] + "series.ics", owner, body, content_type="text/calendar")[0] == 201
    query = (
        '<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        '<d:prop><d:getetag/><c:calendar-data><c:expand start="20301001T000000Z" end="20301031T000000Z"/>'
        '</c:calendar-data></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">'
        '<c:time-range start="20301001T000000Z" end="20301031T000000Z"/></c:comp-filter></c:comp-filter>'
        "</c:filter></c:calendar-query>"
    )
    status, content, _ = dav("REPORT", team["path"], owner, query, DEPTH="1")
    assert status == 207, content
    assert content.count("RECURRENCE-ID") == 3


def test_zones_clients_define_themselves_keep_their_local_times(team: Team) -> None:
    owner = team["users"]["owner"]
    body = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        "BEGIN:VTIMEZONE\r\nTZID:Customized Time Zone\r\n"
        "BEGIN:STANDARD\r\nDTSTART:16010101T030000\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\n"
        "RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10\r\nEND:STANDARD\r\n"
        "BEGIN:DAYLIGHT\r\nDTSTART:16010101T020000\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\n"
        "RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3\r\nEND:DAYLIGHT\r\nEND:VTIMEZONE\r\n"
        "BEGIN:VEVENT\r\nUID:custom-tz\r\nDTSTAMP:20300101T000000Z\r\n"
        "DTSTART;TZID=Customized Time Zone:20301014T090000\r\nDTEND;TZID=Customized Time Zone:20301014T100000\r\n"
        "RRULE:FREQ=WEEKLY;COUNT=4\r\nSUMMARY:Weekly\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    assert dav("PUT", team["path"] + "custom-tz.ics", owner, body, content_type="text/calendar")[0] == 201
    event = Event.objects.get(uid="custom-tz")
    assert event.timezone != "UTC"
    from apps.core.services.recurrence import expand_event

    starts = [s for s, _ in expand_event(event, event.start, event.start + timedelta(days=30))]
    # 09:00 local before and after the clocks go back on 27 October.
    assert [s.astimezone(ZoneInfo(event.timezone)).hour for s in starts] == [9, 9, 9, 9]


def test_events_ending_before_they_start_are_refused(team: Team) -> None:
    owner = team["users"]["owner"]
    body = ics("backwards", start="20301007T100000Z", end="20301007T090000Z")
    assert dav("PUT", team["path"] + "backwards.ics", owner, body, content_type="text/calendar")[0] == 400


def test_attendees_other_than_email_addresses_are_left_out(team: Team) -> None:
    owner = team["users"]["owner"]
    body = ics("people").replace(
        "SUMMARY:Meeting\r\n",
        "SUMMARY:Meeting\r\nORGANIZER:mailto:owner@example.test\r\nATTENDEE:urn:uuid:1234\r\n"
        f"ATTENDEE:mailto:{'a' * 300}@example.org\r\nATTENDEE;PARTSTAT=ACCEPTED:mailto:guest@elsewhere.test\r\n",
    )
    assert dav("PUT", team["path"] + "people.ics", owner, body, content_type="text/calendar")[0] == 201
    assert list(Event.objects.get(uid="people").participants.values_list("email", flat=True)) == [
        "guest@elsewhere.test"
    ]


def test_xml_with_entities_is_a_bad_request(team: Team) -> None:
    body = (
        '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]>'
        '<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>'
    )
    assert dav("PROPFIND", team["path"], team["users"]["owner"], body, DEPTH="0")[0] == 400


def test_principals_name_their_email_address_and_no_address_books(team: Team) -> None:
    owner = team["users"]["owner"]
    body = (
        '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
        'xmlns:cr="urn:ietf:params:xml:ns:carddav"><d:prop><c:calendar-user-address-set/>'
        "<cr:addressbook-home-set/><c:calendar-home-set/></d:prop></d:propfind>"
    )
    status, content, headers = dav("PROPFIND", f"/caldav/{owner.email}/", owner, body, DEPTH="0")
    assert status == 207, content
    assert "mailto:owner@example.test" in content and "addressbook-home-set" not in content
    assert "addressbook" not in dav("OPTIONS", "/caldav/", owner)[2]["DAV"]


def test_calendars_tell_the_viewers_zone(team: Team) -> None:
    owner = team["users"]["owner"]
    owner.timezone = "Europe/Berlin"
    owner.save()
    body = (
        '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><c:calendar-timezone/></d:prop></d:propfind>"
    )
    content = dav("PROPFIND", team["path"], owner, body, DEPTH="0")[1]
    assert "TZID:Europe/Berlin" in content


def test_calendar_names_are_each_owners_own(team: Team) -> None:
    own, owner = team["users"]["own"], team["users"]["owner"]
    assert mkcalendar(owner, f"/caldav/{owner.email}/work/") == 201
    # Another user may use the same name in their own home, and finds out nothing about the other.
    assert mkcalendar(own, f"/caldav/{own.email}/work/") == 201
    mine = Calendar.objects.get(owner=own, dav_name="work")
    assert dav("PUT", f"/caldav/{own.email}/work/e.ics", own, ics("e"), content_type="text/calendar")[0] == 201
    assert Event.objects.get(uid="e").calendar == mine
