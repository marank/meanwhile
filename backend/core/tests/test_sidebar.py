"""
Where calendars and folders sit in the user's sidebar.
"""

import pytest
from django.test import Client

from core.models import CalendarMember, Folder, User
from core.services.calendars import create_calendar

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_client():
    user = User.objects.create_user(email="me@example.test", password="x", display_name="Me")
    client = Client()
    client.force_login(user)
    return user, client


def reorder(client, *items):
    response = client.post("/api/sidebar/reorder", {"items": list(items)}, content_type="application/json")
    assert response.status_code == 200, response.content


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
