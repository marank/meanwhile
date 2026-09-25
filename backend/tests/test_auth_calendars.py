import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "display_name": "Alice", "password": "password123"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert token

    # Login works
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 200

    # Wrong password rejected
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "bad"},
    )
    assert r.status_code == 401


def test_protected_routes_require_auth(client):
    assert client.get("/api/users/me").status_code == 401


def test_create_and_list_calendars(make_calendar):
    auth, cal = make_calendar("owner@example.com", "Vacations")
    assert cal["name"] == "Vacations"
    assert cal["owner_id"]

    r = auth.get("/api/calendars")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["calendar"]["id"] == cal["id"]
    assert data[0]["membership"]["role"] == "owner"


def test_add_member_and_contributor(make_calendar, user_factory, client):
    auth, cal = make_calendar("boss@example.com", "Team")
    user_factory("member@example.com")

    r = auth.post(
        f"/api/calendars/{cal['id']}/members",
        json={"user_id": None, "role": "contributor"},
    )
    assert r.status_code == 422

    # Search user
    r = auth.get("/api/users/search?q=member")
    assert r.status_code == 200
    user_id = r.json()[0]["id"]

    r = auth.post(
        f"/api/calendars/{cal['id']}/members",
        json={"user_id": user_id, "role": "contributor"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "contributor"


def test_create_event_as_contributor(make_calendar, user_factory, client, make_datetime):
    auth, cal = make_calendar("lead@example.com", "Team")
    user_factory("contrib@example.com")
    search = auth.get("/api/users/search?q=contrib")
    uid = search.json()[0]["id"]
    auth.post(f"/api/calendars/{cal['id']}/members", json={"user_id": uid, "role": "contributor"})

    contrib = TestClient(app)
    login = contrib.post(
        "/api/auth/login",
        json={"email": "contrib@example.com", "password": "password123"},
    )
    contrib.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

    start = make_datetime(days=1)
    end = make_datetime(days=1, hour=12)
    r = contrib.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "My vacation", "start": start.isoformat(), "end": end.isoformat()},
    )
    assert r.status_code == 201, r.text


def test_event_timestamps_are_serialized_with_timezone(make_calendar):
    auth, cal = make_calendar("timezone@example.com", "Timezone")
    response = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Midnight",
            "start": "2026-09-28T22:00:00.000Z",
            "end": "2026-09-28T23:00:00.000Z",
        },
    )
    assert response.status_code == 201
    event = response.json()
    assert event["start"].endswith("Z")
    assert event["end"].endswith("Z")

    response = auth.get(f"/api/calendars/events/{event['id']}")
    assert response.status_code == 200
    assert response.json()["start"].endswith("Z")
    assert response.json()["end"].endswith("Z")


def test_all_day_end_date_is_inclusive(make_calendar):
    auth, cal = make_calendar("all-day@example.com", "All day")
    response = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Two days",
            "start": "2026-09-15T00:00:00Z",
            "end": "2026-09-16T00:00:00Z",
            "all_day": True,
        },
    )
    assert response.status_code == 201

    response = auth.get(
        f"/api/calendars/{cal['id']}/events",
        params={"start": "2026-09-01T00:00:00Z", "end": "2026-10-01T00:00:00Z"},
    )
    assert response.status_code == 200
    occurrence = response.json()[0]
    assert occurrence["start"] == "2026-09-15T00:00:00Z"
    assert occurrence["end"] == "2026-09-17T00:00:00Z"


def test_booking_conflict(make_calendar, make_datetime):
    auth, cal = make_calendar("caradmin@example.com", "Cars")
    # Create resource
    r = auth.post(
        f"/api/calendars/{cal['id']}/resources",
        json={"name": "Car A", "requires_approval": True},
    )
    assert r.status_code == 201
    resource = r.json()

    start = make_datetime(days=1, hour=9)
    end = make_datetime(days=1, hour=17)

    # Create approved booking
    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Trip",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r.status_code == 201
    event = r.json()
    assert event["status"] == "pending"

    # Approve as owner
    r = auth.post(f"/api/events/{event['id']}/approve", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # Overlapping booking should be rejected
    r2 = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Overlap",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r2.status_code == 409


def test_booking_conflict_confirmed_resource(make_calendar, make_datetime):
    auth, cal = make_calendar("caradmin2@example.com", "Cars")
    r = auth.post(
        f"/api/calendars/{cal['id']}/resources",
        json={"name": "Car B", "requires_approval": False},
    )
    assert r.status_code == 201
    resource = r.json()

    start = make_datetime(days=1, hour=9)
    end = make_datetime(days=1, hour=17)

    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Confirmed trip",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r.status_code == 201
    assert r.json()["status"] == "confirmed"

    r2 = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Overlap",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r2.status_code == 409


def test_booking_conflict_multi_day(make_calendar, make_datetime):
    auth, cal = make_calendar("caradmin3@example.com", "Cars")
    r = auth.post(
        f"/api/calendars/{cal['id']}/resources",
        json={"name": "Car C", "requires_approval": True},
    )
    assert r.status_code == 201
    resource = r.json()

    start = make_datetime(days=1, hour=9)
    end = make_datetime(days=3, hour=17)

    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Multi-day trip",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r.status_code == 201
    event = r.json()
    assert event["status"] == "pending"

    r = auth.post(f"/api/events/{event['id']}/approve", json={})
    assert r.status_code == 200

    # Booking that starts in the middle of the multi-day reservation
    overlap_start = make_datetime(days=2, hour=10)
    overlap_end = make_datetime(days=2, hour=12)
    r2 = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Mid overlap",
            "start": overlap_start.isoformat(),
            "end": overlap_end.isoformat(),
            "resource_id": resource["id"],
        },
    )
    assert r2.status_code == 409


def test_calendar_can_require_all_day_events(make_calendar):
    auth, cal = make_calendar("all-day-only@example.com", "All day only")
    response = auth.patch(
        f"/api/calendars/{cal['id']}",
        json={
            "force_all_day": True,
            "dark_color": "#60a5fa",
            "first_weekday": 1,
            "show_weekends": False,
            "weekend_days": [4, 5],
            "today_color": "#fef3c7",
            "dark_today_color": "#3f3f46",
            "weekend_color": "#f3f4f6",
            "dark_weekend_color": "#18181b",
        },
    )
    assert response.status_code == 200
    settings = response.json()
    assert settings["force_all_day"] is True
    assert settings["first_weekday"] == 1
    assert settings["show_weekends"] is False
    assert settings["weekend_days"] == [4, 5]
    assert settings["today_color"] == "#fef3c7"
    assert settings["dark_today_color"] == "#3f3f46"
    assert settings["weekend_color"] == "#f3f4f6"
    assert settings["dark_weekend_color"] == "#18181b"

    response = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Timed",
            "start": "2026-09-15T09:00:00Z",
            "end": "2026-09-15T10:00:00Z",
            "all_day": False,
        },
    )
    assert response.status_code == 422


def test_occurrence_can_show_zero_based_recurrence_count(make_calendar):
    auth, cal = make_calendar("birthday@example.com", "Birthdays")
    response = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Birthday",
            "start": "2020-03-15T00:00:00Z",
            "end": "2020-03-15T00:00:00Z",
            "all_day": True,
            "rrule": "FREQ=YEARLY",
            "show_recurrence_count": True,
        },
    )
    assert response.status_code == 201

    response = auth.get(
        f"/api/calendars/{cal['id']}/events",
        params={"start": "2022-01-01T00:00:00Z", "end": "2023-01-01T00:00:00Z"},
    )
    assert response.status_code == 200
    assert response.json()[0]["recurrence_count"] == 2


def test_event_category_is_included_in_occurrences(make_calendar):
    auth, cal = make_calendar("categories@example.com", "Categories")
    response = auth.post(
        f"/api/calendars/{cal['id']}/categories",
        json={"name": "Birthday", "description": "Birthdays", "color": "#ec4899"},
    )
    assert response.status_code == 201
    category = response.json()

    response = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Birthday",
            "start": "2026-09-15T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
            "all_day": True,
            "category_id": category["id"],
        },
    )
    assert response.status_code == 201
    assert response.json()["category_color"] == "#ec4899"

    response = auth.get(
        f"/api/calendars/{cal['id']}/events",
        params={"start": "2026-09-01T00:00:00Z", "end": "2026-10-01T00:00:00Z"},
    )
    assert response.status_code == 200
    occurrence = response.json()[0]
    assert occurrence["category_id"] == category["id"]
    assert occurrence["category_name"] == "Birthday"
    assert occurrence["category_color"] == "#ec4899"


def test_ical_feed(make_calendar):
    auth, cal = make_calendar("feedowner@example.com", "FeedCal")
    r = auth.get(f"/api/calendars/{cal['id']}/feed-url")
    assert r.status_code == 200
    url = r.json()["feed_url"]

    # Feed is public by token
    r = auth.get(url)
    assert r.status_code == 200
    assert "text/calendar" in r.headers["content-type"]
    assert "VERSION:2.0" in r.text
