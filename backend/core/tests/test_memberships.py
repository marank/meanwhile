"""
Memberships from a group or a public calendar follow what they come from; direct ones win over them.
"""

import pytest
from django.test import Client

from core.models import Calendar, CalendarGroup, CalendarMember, Folder, User, UserGroup
from core.services.calendars import create_calendar
from core.services.permissions import get_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    owner = User.objects.create_user(email="owner@example.test", password="x", display_name="Owner")
    me = User.objects.create_user(email="me@example.test", password="x", display_name="Me")
    calendar = create_calendar(owner, "Team")
    group = UserGroup.objects.create(name="Team")
    owner_client, my_client = Client(), Client()
    owner_client.force_login(owner)
    my_client.force_login(me)
    return {"owner": owner, "me": me, "calendar": calendar, "group": group, "api": owner_client, "my": my_client}


def membership(setup):
    return CalendarMember.objects.filter(calendar=setup["calendar"], user=setup["me"]).first()


def access(setup):
    """Where the membership comes from and the role that applies; one from a group or added stores none."""
    row = membership(setup)
    if row is None:
        return None
    if row.source != "direct":
        assert row.role is None
    return row.source, get_membership(setup["calendar"], setup["me"]).role


def sidebar(client):
    return {item["calendar"]["id"]: item for item in client.get("/api/calendars").json()}


def test_joining_a_group_gives_its_calendars_and_leaving_takes_them(setup):
    CalendarGroup.objects.create(calendar=setup["calendar"], group=setup["group"], role="own")
    setup["me"].groups.add(setup["group"])
    assert access(setup) == ("group", "own")
    assert sidebar(setup["my"])[setup["calendar"].id]["access"] == "group"

    setup["me"].groups.remove(setup["group"])
    assert membership(setup) is None
    assert setup["calendar"].id not in sidebar(setup["my"])


def test_the_role_follows_the_best_group(setup):
    setup["me"].groups.add(setup["group"])
    link = CalendarGroup.objects.create(calendar=setup["calendar"], group=setup["group"], role="read")
    assert access(setup) == ("group", "read")

    link.role = "full"
    link.save()
    assert access(setup) == ("group", "full")

    other = UserGroup.objects.create(name="Leads")
    setup["me"].groups.add(other)
    CalendarGroup.objects.create(calendar=setup["calendar"], group=other, role="manage")
    assert access(setup) == ("group", "manage")

    # Taken from the better group, the other one's role applies again; without any, the membership goes.
    CalendarGroup.objects.filter(group=other).delete()
    assert access(setup) == ("group", "full")
    link.delete()
    assert membership(setup) is None


def test_a_direct_membership_wins_and_falls_back_to_the_group_keeping_its_place(setup):
    setup["me"].groups.add(setup["group"])
    CalendarGroup.objects.create(calendar=setup["calendar"], group=setup["group"], role="read")
    folder = Folder.objects.create(user=setup["me"], name="Shared")
    CalendarMember.objects.filter(calendar=setup["calendar"], user=setup["me"]).update(folder=folder)
    cal = setup["calendar"].id

    # Granted directly: the group's membership becomes the direct one, in the same place.
    res = setup["api"].post(f"/api/calendars/{cal}/members", {"user_id": setup["me"].id, "role": "full"}, content_type="application/json")
    assert res.status_code == 200, res.content
    assert (membership(setup).source, membership(setup).role, membership(setup).folder_id) == ("direct", "full", folder.id)
    assert [m["user_id"] for m in setup["api"].get(f"/api/calendars/{cal}/members").json()] == [
        setup["owner"].id,
        setup["me"].id,
    ]
    # A changed group role doesn't touch it.
    CalendarGroup.objects.filter(group=setup["group"]).update(role="own")
    setup["me"].groups.remove(setup["group"])
    setup["me"].groups.add(setup["group"])
    assert access(setup) == ("direct", "full")

    # Taken away again, what the group gives remains, still in the folder.
    assert setup["api"].delete(f"/api/calendars/{cal}/members/{setup['me'].id}").status_code == 200
    assert (access(setup), membership(setup).folder_id) == (("group", "own"), folder.id)
    assert [m["user_id"] for m in setup["api"].get(f"/api/calendars/{cal}/members").json()] == [setup["owner"].id]


def test_an_added_public_calendar_follows_its_public_role_and_leaves_when_private(setup):
    calendar = setup["calendar"]
    calendar.is_public, calendar.public_role = True, "read"
    calendar.save()
    assert setup["my"].put(f"/api/calendars/{calendar.id}/subscription").status_code == 200
    assert access(setup) == ("public", "read")

    calendar.public_role = "own"
    calendar.save()
    assert access(setup) == ("public", "own")

    # Shared through a group meanwhile, it is a group's calendar; without the group, an added public one again.
    setup["me"].groups.add(setup["group"])
    link = CalendarGroup.objects.create(calendar=calendar, group=setup["group"], role="full")
    assert access(setup) == ("group", "full")
    link.delete()
    assert access(setup) == ("public", "own")

    calendar.is_public = False
    calendar.save()
    assert membership(setup) is None


def test_deleting_calendars_and_groups_cleans_up(setup):
    setup["me"].groups.add(setup["group"])
    CalendarGroup.objects.create(calendar=setup["calendar"], group=setup["group"], role="read")
    second = create_calendar(setup["owner"], "Second")
    CalendarGroup.objects.create(calendar=second, group=setup["group"], role="read")

    setup["calendar"].delete()
    assert not Calendar.objects.filter(id=setup["calendar"].id).exists()
    assert CalendarMember.objects.filter(user=setup["me"]).count() == 1

    setup["group"].delete()
    assert not CalendarMember.objects.filter(user=setup["me"]).exists()


def test_access_never_rests_on_a_membership_left_behind(setup):
    # A membership from a group without the group (as if the app had missed a change) grants nothing.
    CalendarMember.objects.create(calendar=setup["calendar"], user=setup["me"], source="group", role=None)
    assert get_membership(setup["calendar"], setup["me"]) is None
    assert setup["calendar"].id not in sidebar(setup["my"])


@pytest.mark.parametrize("clear", ["user.groups", "group.user_set"])
def test_clearing_groups_takes_their_calendars_from_either_side(setup, clear):
    CalendarGroup.objects.create(calendar=setup["calendar"], group=setup["group"], role="read")
    setup["me"].groups.add(setup["group"])
    assert membership(setup) is not None
    if clear == "user.groups":
        setup["me"].groups.clear()
    else:
        setup["group"].user_set.clear()
    assert membership(setup) is None


def test_fixtures_keep_the_memberships_they_bring(setup):
    from django.core import serializers
    from django.utils import timezone

    CalendarMember.objects.create(calendar=setup["calendar"], user=setup["me"], source="public", role=None)
    link = CalendarGroup(calendar=setup["calendar"], group=setup["group"], role="read")
    link.created_at = link.updated_at = timezone.now()  # raw saves don't fill them in
    # Loading a group link (as loaddata does, raw) creates no membership for its group's users...
    setup["group"].user_set.add(User.objects.create_user(email="new@example.test", password="x"))
    for obj in serializers.deserialize("json", serializers.serialize("json", [link])):
        obj.save()
    assert not CalendarMember.objects.filter(user__email="new@example.test").exists()
    # ...and a calendar loaded as private keeps the public membership the fixture has.
    setup["calendar"].is_public = False
    for obj in serializers.deserialize("json", serializers.serialize("json", [setup["calendar"]])):
        obj.save()
    assert membership(setup).source == "public"
