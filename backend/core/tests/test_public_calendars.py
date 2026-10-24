"""
Public calendars show up in a sidebar only once the user added them there.
"""

import pytest

from core.models import Folder
from core.realtime import broadcast
from core.services.permissions import sidebar_calendars

pytestmark = pytest.mark.django_db


@pytest.fixture
def public(world):
    """The world's calendar, made public; "outsider" isn't a member."""
    cal = world["cal"]["id"]
    res = world["api"]["owner"].patch(f"/calendars/{cal}", {"is_public": True, "public_role": "read"})
    assert res.status_code == 200, res.content
    return cal


def listed(world, user="outsider"):
    return {item["calendar"]["id"]: item for item in world["api"][user].get("/calendars").json()}


def offered(world, user="outsider"):
    return {c["id"]: c["added"] for c in world["api"][user].get("/calendars/public").json()}


def test_public_calendars_are_offered_but_not_listed_until_added(world, public):
    assert public not in listed(world)
    assert offered(world) == {public: False}

    assert world["api"]["outsider"].put(f"/calendars/{public}/subscription", {}).status_code == 200
    item = listed(world)[public]
    assert (item["access"], item["membership"]["role"]) == ("public", "read")
    assert offered(world) == {public: True}
    user = world["users"]["outsider"]
    assert sidebar_calendars(user).filter(id=public).exists()  # CalDAV clients list it, too

    assert world["api"]["outsider"].delete(f"/calendars/{public}/subscription").status_code == 200
    assert public not in listed(world)
    assert not sidebar_calendars(user).filter(id=public).exists()


def test_members_are_not_offered_their_own_calendars(world, public):
    assert offered(world, "booker") == {}
    assert listed(world, "booker")[public]["access"] == "member"


def test_an_added_calendar_is_placed_like_any_other(world, public):
    api = world["api"]["outsider"]
    folder = Folder.objects.create(user=world["users"]["outsider"], name="Others")
    api.put(f"/calendars/{public}/subscription", {})
    res = api.patch("/layout/items", {"items": [{"type": "calendar", "id": public, "parent_id": folder.id, "position": 3}]})
    assert res.status_code == 200, res.content
    membership = listed(world)[public]["membership"]
    assert (membership["folder_id"], membership["position"]) == (str(folder.id), 3)


def test_only_public_calendars_can_be_added(world):
    assert world["api"]["outsider"].put(f"/calendars/{world['cal']['id']}/subscription", {}).status_code == 404


def test_a_calendar_made_private_leaves_the_sidebar(world, public):
    world["api"]["outsider"].put(f"/calendars/{public}/subscription", {})
    world["api"]["owner"].patch(f"/calendars/{public}", {"is_public": False})
    assert public not in listed(world)
    assert offered(world) == {}


@pytest.mark.parametrize("remove", ["unsubscribe", "make private"])
def test_whoever_loses_an_added_calendar_hears_of_it(world, public, monkeypatch, remove):
    outsider = world["users"]["outsider"]
    world["api"]["outsider"].put(f"/calendars/{public}/subscription", {})
    told = []
    monkeypatch.setattr(broadcast, "calendars_changed", lambda user_ids: told.extend(user_ids))
    if remove == "unsubscribe":
        world["api"]["outsider"].delete(f"/calendars/{public}/subscription")
    else:
        world["api"]["owner"].patch(f"/calendars/{public}", {"is_public": False})
    assert outsider.id in told
