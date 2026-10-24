"""
The manage role: everything the owner may in a calendar, except deleting it and changing its owner.
"""

import pytest

from core.models import CalendarGroup, UserGroup
from core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager(world):
    """"outsider" manages the calendar, through a group, as managing can be granted like any role."""
    group = UserGroup.objects.create(name="Leads")
    world["users"]["outsider"].groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role="manage")
    return world["api"]["outsider"]


def test_managers_change_settings_access_feed_and_approvers(world, manager):
    cal = world["cal"]["id"]
    users = world["users"]

    assert manager.patch(f"/calendars/{cal}", {"name": "Renamed"}).status_code == 200
    guest = make_user("guest")
    assert manager.post(f"/calendars/{cal}/members", {"user_id": str(guest.id), "role": "manage"}).status_code == 200
    assert manager.patch(f"/calendars/{cal}/members/{users['other'].id}", {"role": "full"}).status_code == 200
    assert manager.delete(f"/calendars/{cal}/members/{users['booker'].id}").status_code == 200
    group = UserGroup.objects.create(name="Guests")
    assert manager.post(f"/calendars/{cal}/groups", {"group_id": str(group.id), "role": "read"}).status_code == 200
    assert manager.post(f"/calendars/{cal}/feed-token/rotate").status_code == 200
    assert manager.put(f"/calendars/{cal}/approvers", {"user_ids": [str(users["approver"].id)]}).status_code == 200


def test_managers_change_all_events(world, manager):
    res = world["book"](world["api"]["booker"], None)
    assert res.status_code == 200, res.content
    assert manager.patch(f"/events/{res.json()['id']}", {"title": "Changed"}).status_code == 200


def test_only_the_owner_deletes_the_calendar_or_is_owner(world, manager):
    cal = world["cal"]["id"]
    owner_id = world["users"]["owner"].id
    me = world["users"]["outsider"].id

    assert manager.delete(f"/calendars/{cal}").status_code == 403
    assert manager.patch(f"/calendars/{cal}/members/{owner_id}", {"role": "read"}).status_code == 400
    assert manager.delete(f"/calendars/{cal}/members/{owner_id}").status_code == 400
    # Nobody becomes a second owner, neither added as one nor promoted to one.
    assert manager.post(f"/calendars/{cal}/members", {"user_id": str(me), "role": "owner"}).status_code == 400
    other = world["users"]["other"].id
    assert manager.patch(f"/calendars/{cal}/members/{other}", {"role": "owner"}).status_code == 400
    assert world["api"]["owner"].patch(f"/calendars/{cal}/members/{other}", {"role": "owner"}).status_code == 400


def test_public_access_never_manages(world):
    res = world["api"]["owner"].patch(f"/calendars/{world['cal']['id']}", {"is_public": True, "public_role": "manage"})
    assert res.status_code == 422


def test_full_access_does_not_manage(world):
    full = world["api"]["full"]
    cal = world["cal"]["id"]
    assert full.patch(f"/calendars/{cal}", {"name": "Renamed"}).status_code == 403
    assert full.patch(f"/calendars/{cal}/members/{world['users']['other'].id}", {"role": "full"}).status_code == 403


def test_only_managers_change_how_resources_are_approved(world, manager):
    cal = world["cal"]["id"]
    room = world["resource"]("Room")
    full = world["api"]["full"]
    url = f"/calendars/{cal}/resources/{room['id']}"

    # Full access edits the resource, but neither turns approval off nor picks the approvers.
    assert full.patch(url, {"name": "Big room"}).status_code == 200
    assert full.patch(url, {"requires_approval": True}).status_code == 200
    assert full.patch(url, {"requires_approval": False}).status_code == 403
    assert full.put(f"{url}/approvers", {"user_ids": [str(world["users"]["full"].id)]}).status_code == 403

    assert manager.patch(url, {"requires_approval": False}).status_code == 200
    assert manager.put(f"{url}/approvers", {"user_ids": [str(world["users"]["approver"].id)]}).status_code == 200
