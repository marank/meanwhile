"""
Where calendars and folders sit in the user's sidebar.
"""

import pytest
from django.test import Client

from core.models import CalendarGroup, CalendarMember, Folder, User, UserGroup
from core.services.calendars import create_calendar

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_client():
    user = User.objects.create_user(email="me@example.test", password="x", display_name="Me")
    client = Client()
    client.force_login(user)
    return user, client


def reorder(client, *items):
    response = client.patch("/api/layout/items", {"items": list(items)}, content_type="application/json")
    assert response.status_code == 200, response.content
    return response


def test_calendars_are_moved_into_folders_by_their_id(user_client):
    user, client = user_client
    calendar = create_calendar(user, "Work")
    folder = Folder.objects.create(user=user, name="Projects")

    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": folder.id, "position": 4})
    membership = CalendarMember.objects.get(calendar=calendar, user=user)
    assert (str(membership.folder_id), membership.position) == (str(folder.id), 4)

    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": None, "position": 0})
    membership.refresh_from_db()
    assert membership.folder_id is None


def listed(client):
    return {item["calendar"]["id"]: item["membership"] for item in client.get("/api/calendars").json()}


def test_calendars_shared_through_a_group_are_moved_too(user_client):
    user, client = user_client
    owner = User.objects.create_user(email="owner@example.test", password="x", display_name="Owner")
    calendar = create_calendar(owner, "Team")
    group = UserGroup.objects.create(name="Team")
    user.groups.add(group)
    CalendarGroup.objects.create(calendar=calendar, group=group, role="read")
    folder = Folder.objects.create(user=user, name="Shared")

    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": folder.id, "position": 2})
    placed = listed(client)[str(calendar.id)]
    assert (placed["folder_id"], placed["position"]) == (str(folder.id), 2)

    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": None, "position": 0})
    assert listed(client)[str(calendar.id)]["folder_id"] is None
    assert CalendarMember.objects.get(calendar=calendar, user=user).source == "group"


def test_calendars_without_access_get_no_place(user_client):
    user, client = user_client
    owner = User.objects.create_user(email="owner@example.test", password="x", display_name="Owner")
    calendar = create_calendar(owner, "Public")
    calendar.is_public = True
    calendar.save()
    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": None, "position": 0})
    # A public calendar shows up in the sidebar by being added, not by being moved there.
    assert calendar.id not in listed(client)


def test_folders_move_into_folders(user_client):
    user, client = user_client
    outer = Folder.objects.create(user=user, name="Outer")
    inner = Folder.objects.create(user=user, name="Inner")
    reorder(client, {"type": "folder", "id": inner.id, "parent_id": outer.id, "position": 0})
    inner.refresh_from_db()
    assert str(inner.parent_id) == str(outer.id)


def test_other_users_sidebars_stay_as_they_are(user_client):
    user, client = user_client
    other = User.objects.create_user(email="other@example.test", password="x", display_name="Other")
    calendar = create_calendar(other, "Theirs")
    folder = Folder.objects.create(user=user, name="Mine")
    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": folder.id, "position": 1})
    assert CalendarMember.objects.get(calendar=calendar, user=other).folder_id is None


def patch(client, url, data):
    return client.patch(f"/api{url}", data, content_type="application/json")


def post(client, url, data):
    return client.post(f"/api{url}", data, content_type="application/json")


def test_the_layout_comes_in_one_request(user_client):
    user, client = user_client
    calendar = create_calendar(user, "Work")
    folder = Folder.objects.create(user=user, name="Projects", position=1)
    Folder.objects.create(user=user, name="First", position=0)
    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": folder.id, "position": 2})

    body = client.get("/api/layout").json()
    assert [f["name"] for f in body["folders"]] == ["First", "Projects"]
    assert [(c["calendar"]["name"], c["membership"]["folder_id"], c["membership"]["position"]) for c in body["calendars"]] == [
        ("Work", str(folder.id), 2)
    ]


def test_the_layout_shows_only_the_users_own_folders(user_client):
    user, client = user_client
    other = User.objects.create_user(email="other@example.test", password="x", display_name="Other")
    Folder.objects.create(user=other, name="Theirs")
    assert client.get("/api/layout").json()["folders"] == []


def test_folders_are_created_renamed_and_deleted(user_client):
    user, client = user_client
    outer = post(client, "/layout/folders", {"name": "Outer"}).json()
    inner = post(client, "/layout/folders", {"name": "Inner", "parent_id": outer["id"], "position": 1}).json()
    assert (inner["parent_id"], inner["position"]) == (outer["id"], 1)

    assert patch(client, f"/layout/folders/{inner['id']}", {"name": "Renamed"}).json()["name"] == "Renamed"
    # Moving to the top level is an explicit null.
    assert patch(client, f"/layout/folders/{inner['id']}", {"parent_id": None}).json()["parent_id"] is None
    assert patch(client, f"/layout/folders/{inner['id']}", {"name": "Again"}).status_code == 200

    calendar = create_calendar(user, "Work")
    reorder(client, {"type": "calendar", "id": calendar.id, "parent_id": outer["id"], "position": 0})
    assert client.delete(f"/api/layout/folders/{outer['id']}").status_code == 200
    assert CalendarMember.objects.get(calendar=calendar, user=user).folder_id is None
    assert [f["name"] for f in client.get("/api/layout").json()["folders"]] == ["Again"]


def test_a_folder_cannot_go_into_itself_or_its_own_folders(user_client):
    user, client = user_client
    outer = Folder.objects.create(user=user, name="Outer")
    inner = Folder.objects.create(user=user, name="Inner", parent=outer)

    assert patch(client, f"/layout/folders/{outer.id}", {"parent_id": outer.id}).status_code == 400
    assert patch(client, f"/layout/folders/{outer.id}", {"parent_id": inner.id}).status_code == 400
    response = client.patch(
        "/api/layout/items",
        {"items": [{"type": "folder", "id": outer.id, "parent_id": inner.id, "position": 0}]},
        content_type="application/json",
    )
    assert response.status_code == 400
    outer.refresh_from_db()
    assert outer.parent_id is None


def test_folders_of_other_users_are_not_usable(user_client):
    user, client = user_client
    other = User.objects.create_user(email="other@example.test", password="x", display_name="Other")
    theirs = Folder.objects.create(user=other, name="Theirs")
    mine = Folder.objects.create(user=user, name="Mine")
    calendar = create_calendar(user, "Work")

    assert post(client, "/layout/folders", {"name": "X", "parent_id": theirs.id}).status_code == 404
    assert patch(client, f"/layout/folders/{mine.id}", {"parent_id": theirs.id}).status_code == 404
    for item in (
        {"type": "folder", "id": mine.id, "parent_id": theirs.id, "position": 0},
        {"type": "calendar", "id": calendar.id, "parent_id": theirs.id, "position": 0},
    ):
        response = client.patch("/api/layout/items", {"items": [item]}, content_type="application/json")
        assert response.status_code == 404
    assert Folder.objects.get(id=theirs.id).name == "Theirs"
    assert CalendarMember.objects.get(calendar=calendar, user=user).folder_id is None


def test_items_that_are_gone_are_skipped(user_client):
    user, client = user_client
    calendar = create_calendar(user, "Work")
    response = client.patch(
        "/api/layout/items",
        {"items": [
            {"type": "folder", "id": "gone", "parent_id": None, "position": 0},
            {"type": "calendar", "id": calendar.id, "parent_id": None, "position": 7},
        ]},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert CalendarMember.objects.get(calendar=calendar, user=user).position == 7
