"""
Listing calendars and their events costs the same however many calendars a user has.
"""

from urllib.parse import quote
from uuid import UUID

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models import CalendarGroup, UserGroup, get_or_create_app_settings
from apps.core.services.calendars import create_calendar
from apps.core.tests.helpers import BASE, Api, World, iso, make_user

pytestmark = pytest.mark.django_db


def queries(api: Api, url: str) -> int:
    with CaptureQueriesContext(connection) as captured:
        assert api.get(url).status_code == 200
    return len(captured)


def test_listing_costs_the_same_for_more_calendars() -> None:
    # Exists in any running app; created by the first listing otherwise (its defaults fill in week layouts).
    get_or_create_app_settings()
    owner, me = make_user("owner"), make_user("me")
    group = UserGroup.objects.create(name="Team")
    me.groups.add(group)
    api = Api(me)
    calendar_ids: list[UUID] = []

    def add_calendars(n: int) -> None:
        for _ in range(n):
            shared = create_calendar(owner, f"Shared {len(calendar_ids)}")
            CalendarGroup.objects.create(calendar=shared, group=group, role="read")
            mine = create_calendar(me, f"Mine {len(calendar_ids)}")
            calendar_ids.extend([shared.id, mine.id])
            for calendar in (shared, mine):
                Api(calendar.owner).post(
                    f"/calendars/{calendar.id}/events",
                    {
                        "title": "Meeting",
                        "start": iso(BASE),
                        "end": iso(BASE.replace(hour=10)),
                    },
                )

    def events_url() -> str:
        ids = "&".join(f"calendar_ids={i}" for i in calendar_ids)
        return f"/events?start={quote(iso(BASE.replace(hour=0)))}&end={quote(iso(BASE.replace(hour=23)))}&{ids}"

    add_calendars(2)
    few = queries(api, "/calendars"), queries(api, events_url())
    add_calendars(10)
    assert (queries(api, "/calendars"), queries(api, events_url())) == few


def test_listing_approvals_costs_the_same_for_more_bookings(world: World) -> None:
    room = world["resource"]("Room", approver_ids=[str(world["users"]["resapprover"].id)])
    projector = world["resource"]("Projector")
    api = world["api"]["owner"]

    def book(n: int, offset: int) -> None:
        for i in range(n):
            for resource in (room, projector):
                res = world["book"](world["api"]["booker"], resource["id"], start=BASE.replace(day=1 + offset + i))
                assert res.status_code == 200, res.content

    book(2, 0)
    few = queries(api, "/approvals")
    book(8, 2)
    assert queries(api, "/approvals") == few
