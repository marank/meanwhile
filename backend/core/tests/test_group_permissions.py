"""
Roles granted through a group: they allow exactly what the same role granted directly allows.
"""

from datetime import timedelta

import pytest

from core.models import CalendarGroup, UserGroup
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db


def grant_via_group(world, user, role):
    group = UserGroup.objects.create(name=f"Team {role}")
    world["users"][user].groups.add(group)
    CalendarGroup.objects.create(calendar_id=world["cal"]["id"], group=group, role=role)


def create_event(world):
    data = {"title": "Planning", "start": iso(BASE), "end": iso(BASE + timedelta(hours=1)), "timezone": "UTC"}
    res = world["api"]["owner"].post(f"/calendars/{world['cal']['id']}/events", data)
    assert res.status_code == 200, res.content
    return res.json()


def test_read_through_a_group_sees_events_but_cannot_change_them(world):
    grant_via_group(world, "outsider", "read")
    event = create_event(world)
    api = world["api"]["outsider"]

    assert api.get(f"/events/{event['id']}").status_code == 200
    assert api.patch(f"/events/{event['id']}", {"title": "Changed"}).status_code == 403
    assert api.delete(f"/events/{event['id']}").status_code == 403
    assert world["api"]["owner"].get(f"/events/{event['id']}").json()["title"] == "Planning"


def test_full_through_a_group_can_change_events(world):
    grant_via_group(world, "outsider", "full")
    event = create_event(world)

    res = world["api"]["outsider"].patch(f"/events/{event['id']}", {"title": "Changed"})
    assert res.status_code == 200, res.content
    assert res.json()["title"] == "Changed"
