"""
Live updates over WebSockets, through the ASGI application the server runs.
"""

import base64
import contextlib
from datetime import UTC, datetime
from typing import Any, TypedDict

import pytest
from channels.db import database_sync_to_async
from django.db import transaction
from django.test import Client

from apps.core.models import AppPassword, Calendar, CalendarMember, Event, Notification, User
from apps.core.services import app_passwords
from apps.core.services.reminders import deliver_due_reminders
from apps.core.tests.asgi import HttpCommunicator, WebsocketCommunicator
from apps.core.tests.helpers import Response

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

ORIGIN = b"http://localhost:6326"


class Team(TypedDict):
    owner: User
    other: User
    calendar: Calendar
    private: Calendar
    session: str


@pytest.fixture
def team() -> Team:
    owner = User.objects.create_user(email="owner@example.test", password="pw", display_name="Owner")
    other = User.objects.create_user(email="other@example.test", password="pw", display_name="Other")
    AppPassword.objects.create(user=owner, label="Tests", token_hash=app_passwords.token_hash("app-token"))
    calendar = Calendar.objects.create(name="Team", owner=owner)
    CalendarMember.objects.create(calendar=calendar, user=owner, role="owner")
    private = Calendar.objects.create(name="Private", owner=other)
    CalendarMember.objects.create(calendar=private, user=other, role="owner")
    client = Client()
    client.force_login(owner)
    return {
        "owner": owner,
        "other": other,
        "calendar": calendar,
        "private": private,
        "session": client.cookies["sessionid"].value,
    }


def socket(session: str | None = None, origin: bytes = ORIGIN) -> WebsocketCommunicator:
    headers = [(b"host", b"localhost:8000"), (b"origin", origin)]
    if session:
        headers.append((b"cookie", f"sessionid={session}".encode()))
    return WebsocketCommunicator("/ws/", headers=headers)


async def connected(team: Team) -> WebsocketCommunicator:
    communicator = socket(team["session"])
    accepted, _ = await communicator.connect()
    assert accepted
    assert await communicator.receive_json_from() == {"type": "hello", "protocol": 1}
    return communicator


async def subscribe(communicator: WebsocketCommunicator, *calendar_ids: object) -> list[str]:
    await communicator.send_json_to({"type": "subscribe", "calendars": [str(i) for i in calendar_ids]})
    reply = await communicator.receive_json_from()
    assert reply["type"] == "subscribed"
    calendars: list[str] = reply["calendars"]
    return calendars


@database_sync_to_async
def create_event(calendar: Calendar, title: str = "Meeting") -> Event:
    return Event.objects.create(
        calendar=calendar,
        creator=calendar.owner,
        title=title,
        uid=title,
        start=datetime(2030, 1, 7, 9, tzinfo=UTC),
        end=datetime(2030, 1, 7, 10, tzinfo=UTC),
    )


async def test_without_a_session_the_socket_closes(team: Team) -> None:
    communicator = socket()
    accepted, _ = await communicator.connect()
    assert accepted
    assert (await communicator.receive_output())["code"] == 4401


async def test_pages_of_other_sites_cannot_connect(team: Team) -> None:
    communicator = socket(team["session"], origin=b"https://evil.example")
    accepted, code = await communicator.connect()
    assert not accepted and code == 4403


async def test_only_readable_calendars_are_followed(team: Team) -> None:
    communicator = await connected(team)
    assert await subscribe(communicator, team["calendar"].id, team["private"].id, "nonsense") == [
        str(team["calendar"].id)
    ]
    await communicator.disconnect()


async def test_changes_of_followed_calendars_arrive(team: Team) -> None:
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    await create_event(team["calendar"])
    assert await communicator.receive_json_from() == {"type": "events.changed", "calendar_id": str(team["calendar"].id)}

    await create_event(team["private"])
    assert await communicator.receive_nothing()

    # Following other calendars stops the earlier ones.
    await subscribe(communicator)
    await create_event(team["calendar"], "Later")
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_a_transaction_is_announced_once(team: Team) -> None:
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    @database_sync_to_async
    def several() -> None:
        with transaction.atomic():
            for i in range(3):
                Event.objects.create(
                    calendar=team["calendar"],
                    creator=team["owner"],
                    title=f"E{i}",
                    uid=f"e{i}",
                    start=datetime(2030, 1, 7, 9, tzinfo=UTC),
                    end=datetime(2030, 1, 7, 10, tzinfo=UTC),
                )

    await several()
    assert (await communicator.receive_json_from())["type"] == "events.changed"
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_changes_rolled_back_are_not_announced(team: Team) -> None:
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    def create_and_fail() -> None:
        with transaction.atomic():
            Event.objects.create(
                calendar=team["calendar"],
                creator=team["owner"],
                title="Gone",
                uid="gone",
                start=datetime(2030, 1, 7, 9, tzinfo=UTC),
                end=datetime(2030, 1, 7, 10, tzinfo=UTC),
            )
            raise RuntimeError

    @database_sync_to_async
    def rolled_back() -> None:
        with transaction.atomic(), contextlib.suppress(RuntimeError):
            create_and_fail()
        # A later change still goes out.
        Event.objects.create(
            calendar=team["calendar"],
            creator=team["owner"],
            title="Kept",
            uid="kept",
            start=datetime(2030, 1, 7, 9, tzinfo=UTC),
            end=datetime(2030, 1, 7, 10, tzinfo=UTC),
        )

    await rolled_back()
    assert (await communicator.receive_json_from())["type"] == "events.changed"
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_losing_access_ends_the_subscription(team: Team) -> None:
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    @database_sync_to_async
    def hand_over() -> None:
        # The calendar goes to someone else; the former owner keeps no membership.
        CalendarMember.objects.filter(calendar=team["calendar"], user=team["owner"]).delete()
        Calendar.objects.filter(pk=team["calendar"].pk).update(owner=team["other"])

    await hand_over()
    # The membership ending changes the list of calendars, too.
    assert await communicator.receive_json_from() == {"type": "calendars.changed"}
    await create_event(team["calendar"])
    assert await communicator.receive_json_from() == {"type": "subscribed", "calendars": []}
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_notifications_are_announced_to_their_user(team: Team) -> None:
    communicator = await connected(team)
    await database_sync_to_async(Notification.objects.create)(user=team["owner"], type="comment_added", title="x")
    assert await communicator.receive_json_from() == {"type": "notifications.changed"}
    await database_sync_to_async(Notification.objects.create)(user=team["other"], type="comment_added", title="x")
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_ping_checks_the_session(team: Team) -> None:
    communicator = await connected(team)
    await communicator.send_json_to({"type": "ping"})
    assert await communicator.receive_json_from() == {"type": "pong"}

    @database_sync_to_async
    def log_out() -> None:
        from django.contrib.sessions.models import Session

        Session.objects.filter(session_key=team["session"]).delete()

    await log_out()
    await communicator.send_json_to({"type": "ping"})
    assert (await communicator.receive_output())["code"] == 4401


async def test_bad_messages_are_answered_not_fatal(team: Team) -> None:
    communicator = await connected(team)
    await communicator.send_to(text_data="not json")
    assert (await communicator.receive_json_from())["type"] == "error"
    await communicator.send_json_to({"type": "subscribe", "calendars": "all"})
    assert (await communicator.receive_json_from())["type"] == "error"
    await communicator.send_json_to({"type": "dance"})
    assert (await communicator.receive_json_from())["type"] == "error"
    await communicator.send_json_to({"type": "ping"})
    assert await communicator.receive_json_from() == {"type": "pong"}
    await communicator.disconnect()


async def test_caldav_is_served_through_asgi(team: Team) -> None:
    auth = base64.b64encode(b"owner@example.test:app-token")
    communicator = HttpCommunicator(
        "PROPFIND",
        "/caldav/owner@example.test/",
        body=b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>',
        headers=[(b"authorization", b"Basic " + auth), (b"depth", b"1"), (b"host", b"localhost:8000")],
    )
    response = await communicator.get_response(timeout=10)
    assert response["status"] == 207
    assert f"{team['calendar'].id}/".encode() in response["body"]

    communicator = HttpCommunicator("GET", "/api/users/me", headers=[(b"host", b"localhost:8000")])
    assert (await communicator.get_response())["status"] == 401
    # Django waits for the client to go away after answering, as a real one would.
    await communicator.send_input({"type": "http.disconnect"})
    await communicator.wait()


async def test_the_list_of_calendars_follows_access_and_settings(team: Team) -> None:
    from apps.core.models import CalendarGroup, Folder, UserGroup

    communicator = await connected(team)
    expected = {"type": "calendars.changed"}

    @database_sync_to_async
    def act(step: str) -> None:
        calendar, other = team["calendar"], team["other"]
        if step == "shared":
            CalendarMember.objects.create(calendar=calendar, user=team["other"], role="read")
        elif step == "renamed":
            calendar.name = "Renamed"
            calendar.save()
        elif step == "folder":
            Folder.objects.create(user=team["owner"], name="Work")
        elif step == "group":
            group = UserGroup.objects.create(name="Crew")
            team["owner"].groups.add(group)
            CalendarGroup.objects.create(calendar=team["private"], group=group, role="read")
        elif step == "left":
            CalendarMember.objects.filter(calendar=calendar, user=other).delete()

    # Changes of the owner's own list arrive; those of other users' lists don't.
    await act("folder")
    assert await communicator.receive_json_from() == expected
    assert await communicator.receive_nothing()

    await act("renamed")
    assert await communicator.receive_json_from() == expected
    assert await communicator.receive_nothing()

    await act("shared")
    assert await communicator.receive_nothing()
    await act("left")
    assert await communicator.receive_nothing()

    # Joining a group that is linked to a calendar gives access to it.
    await act("group")
    assert await communicator.receive_json_from() == expected
    await communicator.disconnect()


async def test_reordering_the_sidebar_updates_the_users_other_tabs(team: Team) -> None:
    communicator = await connected(team)

    @database_sync_to_async
    def reorder() -> Response:
        client = Client()
        client.force_login(team["owner"])
        return client.patch(
            "/api/layout/items",
            {"items": [{"type": "calendar", "id": team["calendar"].id, "position": 3, "parent_id": None}]},
            content_type="application/json",
        )

    assert (await reorder()).status_code == 200
    assert await communicator.receive_json_from() == {"type": "calendars.changed"}
    await communicator.disconnect()


@database_sync_to_async
def remind_in(team: Team, minutes_from_now: int, before: int = 15) -> Event:
    from datetime import timedelta

    from apps.core.models import EventReminder

    start = datetime.now(UTC) + timedelta(minutes=minutes_from_now)
    event = Event.objects.create(
        calendar=team["calendar"],
        creator=team["owner"],
        title="Soon",
        uid=f"soon-{minutes_from_now}",
        start=start,
        end=start + timedelta(hours=1),
    )
    EventReminder.objects.create(event=event, user=team["owner"], minutes_before=before)
    return event


async def receive_until(communicator: WebsocketCommunicator, message_type: str, limit: int = 6) -> dict[str, Any]:
    for _ in range(limit):
        message: dict[str, Any] = await communicator.receive_json_from()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"no {message_type} message")


@database_sync_to_async
def session_of(user: User) -> str:
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


async def test_reminders_reach_every_connection_of_the_user_and_nobody_else(team: Team) -> None:
    first, second = await connected(team), await connected(team)
    other_socket = socket(await session_of(team["other"]))
    await other_socket.connect()
    await other_socket.receive_json_from()

    await remind_in(team, 10)
    # The regular job (apps.core.tasks.deliver_reminders) hands them out; the user's group tells both connections.
    assert len(await database_sync_to_async(deliver_due_reminders)()) == 1
    for communicator in (first, second):
        message = await receive_until(communicator, "reminders.due")
        assert [r["title"] for r in message["reminders"]] == ["Soon"]
        assert message["reminders"][0]["minutes_before"] == 15
    assert await other_socket.receive_nothing(timeout=0.5)

    # Handed out once: the next run doesn't repeat it.
    assert await database_sync_to_async(deliver_due_reminders)() == []
    assert await first.receive_nothing(timeout=0.5)
    for communicator in (first, second, other_socket):
        await communicator.disconnect()
