"""
The public iCal feed: what subscribers see and how they poll it.
"""

from datetime import UTC, datetime

import pytest
from django.test import Client

from core.models import Calendar, CalendarMember, Category, Event, FeedToken, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def calendar():
    owner = User.objects.create_user(email="owner@example.test", password="x")
    calendar = Calendar.objects.create(name="Team Ä", description="Our dates", owner=owner, event_color="#3372cc")
    CalendarMember.objects.create(calendar=calendar, user=owner, role="owner")
    FeedToken.objects.create(calendar=calendar, user=owner, token="tok")
    Event.objects.create(
        calendar=calendar, creator=owner, title="Meeting", uid="m",
        start=datetime(2030, 1, 7, 9, tzinfo=UTC), end=datetime(2030, 1, 7, 10, tzinfo=UTC),
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

    # The feed's version follows updated_at (as CalDAV's sync does), which every change of the app sets.
    event = Event.objects.get(uid="m")
    event.title = "Moved"
    event.save()
    changed = client.get("/ics/tok.ics", HTTP_IF_NONE_MATCH=first["ETag"])
    assert changed.status_code == 200 and changed["ETag"] != first["ETag"]


def test_renaming_a_category_changes_the_feed(calendar):
    category = Category.objects.create(calendar=calendar, name="Work")
    Event.objects.filter(uid="m").update(category=category)  # as of the fixture: already in the feed
    client = Client()
    first = client.get("/ics/tok.ics")
    category.name = "Office"
    category.save()
    changed = client.get("/ics/tok.ics", HTTP_IF_NONE_MATCH=first["ETag"])
    assert changed.status_code == 200 and "CATEGORIES:Office" in changed.content.decode()


def test_unknown_feed(calendar):
    assert Client().get("/ics/nope.ics").status_code == 404


def test_feed_urls_are_personal_and_end_with_access(world):
    cal = world["cal"]["id"]
    owner, full = world["api"]["owner"], world["api"]["full"]
    mine = owner.get(f"/calendars/{cal}/feed-url").json()["feed_url"]
    theirs = full.get(f"/calendars/{cal}/feed-url").json()["feed_url"]
    assert mine != theirs
    # The same URL every time, until the user asks for a new one.
    assert full.get(f"/calendars/{cal}/feed-url").json()["feed_url"] == theirs
    path = theirs.split("://", 1)[1].split("/", 1)[1]
    assert Client().get(f"/{path}").status_code == 200

    assert owner.delete(f"/calendars/{cal}/members/{world['users']['full'].id}").status_code == 200
    assert Client().get(f"/{path}").status_code == 404
    mine_path = mine.split("://", 1)[1].split("/", 1)[1]
    assert Client().get(f"/{mine_path}").status_code == 200


def test_rotating_replaces_only_the_users_own_url(world):
    cal = world["cal"]["id"]
    full = world["api"]["full"]
    old = full.get(f"/calendars/{cal}/feed-url").json()["feed_url"]
    new = full.post(f"/calendars/{cal}/feed-token/rotate").json()["feed_url"]
    assert new != old
    assert Client().get("/" + old.split("://", 1)[1].split("/", 1)[1]).status_code == 404
