"""
The public iCal feed: what subscribers see and how they poll it.
"""

from datetime import datetime, timezone

import pytest
from django.test import Client

from core.models import Calendar, Event, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def calendar():
    owner = User.objects.create_user(email="owner@example.test", password="x")
    calendar = Calendar.objects.create(name="Team Ä", description="Our dates", owner=owner, feed_token="tok", event_color="#3372cc")
    Event.objects.create(
        calendar=calendar, creator=owner, title="Meeting", uid="m",
        start=datetime(2030, 1, 7, 9, tzinfo=timezone.utc), end=datetime(2030, 1, 7, 10, tzinfo=timezone.utc),
    )
    return calendar


def test_feed_names_the_calendar(calendar):
    response = Client().get("/ics/tok.ics")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar; charset=utf-8"
    body = response.content.decode()
    assert "X-WR-CALNAME:Team Ä" in body and "NAME:Team Ä" in body
    assert "X-WR-CALDESC:Our dates" in body
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT1H" in body and "X-PUBLISHED-TTL:PT1H" in body
    assert "X-APPLE-CALENDAR-COLOR:#3372cc" in body


def test_unchanged_feed_answers_not_modified(calendar):
    client = Client()
    first = client.get("/ics/tok.ics")
    assert first["Cache-Control"] == "no-cache"
    assert client.get("/ics/tok.ics", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304
    assert client.get("/ics/tok.ics", HTTP_IF_MODIFIED_SINCE=first["Last-Modified"]).status_code == 304

    Event.objects.filter(uid="m").update(title="Moved")
    changed = client.get("/ics/tok.ics", HTTP_IF_NONE_MATCH=first["ETag"])
    assert changed.status_code == 200 and changed["ETag"] != first["ETag"]


def test_unknown_feed(calendar):
    assert Client().get("/ics/nope.ics").status_code == 404
