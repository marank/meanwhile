"""
Optional texts are stored as "" (never NULL); clients may still send null for "none".
"""

import pytest

from core.models import Calendar, Event
from core.tests.helpers import BASE, iso

pytestmark = pytest.mark.django_db


def test_null_texts_are_stored_empty(world):
    owner, cal = world["api"]["owner"], world["cal"]["id"]
    assert owner.patch(f"/calendars/{cal}", {"description": None}).json()["description"] == ""
    assert Calendar.objects.get(id=cal).description == ""

    event = owner.post(f"/calendars/{cal}/events", {
        "title": "Plan", "description": None, "start": iso(BASE), "end": iso(BASE.replace(hour=10)),
    }).json()
    assert event["description"] == ""
    owner.patch(f"/events/{event['id']}", {"description": "Agenda"})
    owner.patch(f"/events/{event['id']}", {"description": None})
    assert Event.objects.get(id=event["id"]).description == ""


def test_app_settings_accept_null_urls(world):
    world["users"]["owner"].is_admin = True
    world["users"]["owner"].save()
    res = world["api"]["owner"].patch("/admin/settings", {"logo_url": None, "favicon_url": None})
    assert res.status_code == 200, res.content
    assert (res.json()["logo_url"], res.json()["favicon_url"]) == ("", "")
