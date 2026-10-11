"""
Live updates over WebSockets, through the ASGI application the server runs.
"""

import base64
import json
from datetime import datetime, timezone

import pytest
from channels.db import database_sync_to_async
from channels.testing import HttpCommunicator, WebsocketCommunicator
from django.db import transaction
from django.test import Client

from config.asgi import application
from core.models import Calendar, CalendarMember, Event, Notification, User

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

ORIGIN = b"http://localhost:5173"


@pytest.fixture
def team():
    owner = User.objects.create_user(email="owner@example.test", password="pw", display_name="Owner")
    other = User.objects.create_user(email="other@example.test", password="pw", display_name="Other")
    calendar = Calendar.objects.create(name="Team", owner=owner, feed_token="t1")
    CalendarMember.objects.create(calendar=calendar, user=owner, role="owner")
    private = Calendar.objects.create(name="Private", owner=other, feed_token="t2")
    CalendarMember.objects.create(calendar=private, user=other, role="owner")
    client = Client()
    client.force_login(owner)
    return {"owner": owner, "other": other, "calendar": calendar, "private": private, "session": client.cookies["sessionid"].value}


def socket(session: str | None = None, origin: bytes = ORIGIN) -> WebsocketCommunicator:
    headers = [(b"host", b"localhost:8000"), (b"origin", origin)]
    if session:
        headers.append((b"cookie", f"sessionid={session}".encode()))
    return WebsocketCommunicator(application, "/ws/", headers=headers)


async def connected(team) -> WebsocketCommunicator:
    communicator = socket(team["session"])
    accepted, _ = await communicator.connect()
    assert accepted
    assert await communicator.receive_json_from() == {"type": "hello", "protocol": 1}
    return communicator


async def subscribe(communicator, *calendar_ids) -> list[str]:
    await communicator.send_json_to({"type": "subscribe", "calendars": list(calendar_ids)})
    reply = await communicator.receive_json_from()
    assert reply["type"] == "subscribed"
    return reply["calendars"]


@database_sync_to_async
def create_event(calendar: Calendar, title: str = "Meeting") -> Event:
    event = Event.objects.create(
        calendar=calendar, creator=calendar.owner, title=title, uid=title,
        start=datetime(2030, 1, 7, 9, tzinfo=timezone.utc), end=datetime(2030, 1, 7, 10, tzinfo=timezone.utc),
    )
    return event


async def test_without_a_session_the_socket_closes(team):
    communicator = socket()
    accepted, _ = await communicator.connect()
    assert accepted
    assert (await communicator.receive_output())["code"] == 4401


async def test_pages_of_other_sites_cannot_connect(team):
    communicator = socket(team["session"], origin=b"https://evil.example")
    accepted, code = await communicator.connect()
    assert not accepted and code == 4403


async def test_only_readable_calendars_are_followed(team):
    communicator = await connected(team)
    assert await subscribe(communicator, team["calendar"].id, team["private"].id, "nonsense") == [team["calendar"].id]
    await communicator.disconnect()


async def test_changes_of_followed_calendars_arrive(team):
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    await create_event(team["calendar"])
    assert await communicator.receive_json_from() == {"type": "events.changed", "calendar_id": team["calendar"].id}

    await create_event(team["private"])
    assert await communicator.receive_nothing()

    # Following other calendars stops the earlier ones.
    await subscribe(communicator)
    await create_event(team["calendar"], "Later")
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_a_transaction_is_announced_once(team):
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    @database_sync_to_async
    def several():
        with transaction.atomic():
            for i in range(3):
                Event.objects.create(
                    calendar=team["calendar"], creator=team["owner"], title=f"E{i}", uid=f"e{i}",
                    start=datetime(2030, 1, 7, 9, tzinfo=timezone.utc), end=datetime(2030, 1, 7, 10, tzinfo=timezone.utc),
                )

    await several()
    assert (await communicator.receive_json_from())["type"] == "events.changed"
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_changes_rolled_back_are_not_announced(team):
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    @database_sync_to_async
    def rolled_back():
        with transaction.atomic():
            try:
                with transaction.atomic():
                    Event.objects.create(
                        calendar=team["calendar"], creator=team["owner"], title="Gone", uid="gone",
                        start=datetime(2030, 1, 7, 9, tzinfo=timezone.utc), end=datetime(2030, 1, 7, 10, tzinfo=timezone.utc),
                    )
                    raise RuntimeError
            except RuntimeError:
                pass
        # A later change still goes out.
        Event.objects.create(
            calendar=team["calendar"], creator=team["owner"], title="Kept", uid="kept",
            start=datetime(2030, 1, 7, 9, tzinfo=timezone.utc), end=datetime(2030, 1, 7, 10, tzinfo=timezone.utc),
        )

    await rolled_back()
    assert (await communicator.receive_json_from())["type"] == "events.changed"
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_losing_access_ends_the_subscription(team):
    communicator = await connected(team)
    await subscribe(communicator, team["calendar"].id)

    @database_sync_to_async
    def hand_over():
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


async def test_notifications_are_announced_to_their_user(team):
    communicator = await connected(team)
    await database_sync_to_async(Notification.objects.create)(user=team["owner"], type="comment_added", title="x")
    assert await communicator.receive_json_from() == {"type": "notifications.changed"}
    await database_sync_to_async(Notification.objects.create)(user=team["other"], type="comment_added", title="x")
    assert await communicator.receive_nothing()
    await communicator.disconnect()


async def test_ping_checks_the_session(team):
    communicator = await connected(team)
    await communicator.send_json_to({"type": "ping"})
    assert await communicator.receive_json_from() == {"type": "pong"}

    @database_sync_to_async
    def log_out():
        from django.contrib.sessions.models import Session

        Session.objects.filter(session_key=team["session"]).delete()

    await log_out()
    await communicator.send_json_to({"type": "ping"})
    assert (await communicator.receive_output())["code"] == 4401


async def test_bad_messages_are_answered_not_fatal(team):
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


async def test_caldav_is_served_through_asgi(team):
    auth = base64.b64encode(b"owner@example.test:pw")
    communicator = HttpCommunicator(
        application,
        "PROPFIND",
        "/caldav/owner@example.test/",
        body=b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>',
        headers=[(b"authorization", b"Basic " + auth), (b"depth", b"1"), (b"host", b"localhost:8000")],
    )
    response = await communicator.get_response(timeout=10)
    assert response["status"] == 207
    assert f"{team['calendar'].id}/".encode() in response["body"]

    communicator = HttpCommunicator(application, "GET", "/api/users/me", headers=[(b"host", b"localhost:8000")])
    assert (await communicator.get_response())["status"] == 401
    # Django waits for the client to go away after answering, as a real one would.
    await communicator.send_input({"type": "http.disconnect"})
    await communicator.wait()


async def test_the_list_of_calendars_follows_access_and_settings(team):
    from core.models import CalendarGroup, Folder, UserGroup

    communicator = await connected(team)
    expected = {"type": "calendars.changed"}

    @database_sync_to_async
    def act(step):
        calendar, other = team["calendar"], team["other"]
        if step == "shared":
            CalendarMember.objects.create(calendar=calendar, user=team["other"], role="viewer")
        elif step == "renamed":
            calendar.name = "Renamed"
            calendar.save()
        elif step == "folder":
            Folder.objects.create(user=team["owner"], name="Work")
        elif step == "group":
            group = UserGroup.objects.create(name="Crew")
            team["owner"].groups.add(group)
            CalendarGroup.objects.create(calendar=team["private"], group=group, role="viewer")
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


async def test_reordering_the_sidebar_updates_the_users_other_tabs(team):
    communicator = await connected(team)

    @database_sync_to_async
    def reorder():
        client = Client()
        client.force_login(team["owner"])
        return client.post(
            "/api/sidebar/reorder",
            {"items": [{"type": "calendar", "id": team["calendar"].id, "position": 3, "parent_id": None}]},
            content_type="application/json",
        )

    assert (await reorder()).status_code == 200
    assert await communicator.receive_json_from() == {"type": "calendars.changed"}
    await communicator.disconnect()
