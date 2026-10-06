def _events(auth, cal_id, start, end):
    r = auth.get(f"/api/calendars/{cal_id}/events", params={"start": start, "end": end})
    assert r.status_code == 200, r.text
    return r.json()


def _feed(auth, cal_id):
    url = auth.get(f"/api/calendars/{cal_id}/feed-url").json()["feed_url"]
    r = auth.get(url)
    assert r.status_code == 200
    assert "text/calendar" in r.headers["content-type"]
    return r.text


def test_contributor_can_create_viewer_cannot(make_calendar, add_member, at):
    owner, cal = make_calendar("lead@example.com", "Team")
    contrib = add_member(owner, cal["id"], "contrib@example.com", "contributor")
    viewer = add_member(owner, cal["id"], "viewer@example.com", "viewer")
    body = {"title": "Vacation", "start": at(1).isoformat(), "end": at(1, hour=12).isoformat()}

    assert contrib.post(f"/api/calendars/{cal['id']}/events", json=body).status_code == 201
    assert viewer.post(f"/api/calendars/{cal['id']}/events", json=body).status_code == 403


def test_contributor_can_only_edit_own_events(make_calendar, add_member, at):
    owner, cal = make_calendar("lead2@example.com", "Team")
    contrib = add_member(owner, cal["id"], "contrib2@example.com", "contributor")
    body = {"title": "Owner's", "start": at(1).isoformat(), "end": at(1, hour=12).isoformat()}
    owners_event = owner.post(f"/api/calendars/{cal['id']}/events", json=body).json()

    r = contrib.patch(f"/api/calendars/events/{owners_event['id']}", json={"title": "Hijacked"})
    assert r.status_code == 403


def test_event_timestamps_are_serialized_with_timezone(make_calendar):
    auth, cal = make_calendar("timezone@example.com", "Timezone")
    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Midnight", "start": "2026-09-28T22:00:00.000Z", "end": "2026-09-28T23:00:00.000Z"},
    )
    assert r.status_code == 201
    assert r.json()["start"] == "2026-09-28T22:00:00Z"

    r = auth.get(f"/api/calendars/events/{r.json()['id']}")
    assert r.json()["start"] == "2026-09-28T22:00:00Z"
    assert r.json()["end"] == "2026-09-28T23:00:00Z"


def test_all_day_end_date_is_inclusive(make_calendar):
    auth, cal = make_calendar("all-day@example.com", "All day")
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Two days", "start": "2026-09-15T00:00:00Z", "end": "2026-09-16T00:00:00Z", "all_day": True},
    )
    [occurrence] = _events(auth, cal["id"], "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z")
    assert occurrence["start"] == "2026-09-15T00:00:00Z"
    assert occurrence["end"] == "2026-09-17T00:00:00Z"


def test_all_day_event_visible_on_inclusive_last_day(make_calendar):
    auth, cal = make_calendar("allday-last@example.com", "AllDay")
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Two days", "start": "2026-09-15T00:00:00Z", "end": "2026-09-16T00:00:00Z", "all_day": True},
    )
    # A day view for a UTC-5 user on 09-16 starts after the stored end.
    occurrences = _events(auth, cal["id"], "2026-09-16T05:00:00Z", "2026-09-17T05:00:00Z")
    assert [o["title"] for o in occurrences] == ["Two days"]


def test_events_outside_range_are_excluded(make_calendar):
    auth, cal = make_calendar("range@example.com", "Range")
    for title, day in (("Before", "01"), ("Inside", "15"), ("After", "30")):
        auth.post(
            f"/api/calendars/{cal['id']}/events",
            json={"title": title, "start": f"2026-09-{day}T10:00:00Z", "end": f"2026-09-{day}T11:00:00Z"},
        )
    occurrences = _events(auth, cal["id"], "2026-09-10T00:00:00Z", "2026-09-20T00:00:00Z")
    assert [o["title"] for o in occurrences] == ["Inside"]


def test_calendar_can_require_all_day_events(make_calendar):
    auth, cal = make_calendar("all-day-only@example.com", "All day only")
    auth.patch(f"/api/calendars/{cal['id']}", json={"force_all_day": True})
    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Timed", "start": "2026-09-15T09:00:00Z", "end": "2026-09-15T10:00:00Z", "all_day": False},
    )
    assert r.status_code == 422


def test_occurrence_can_show_zero_based_recurrence_count(make_calendar):
    auth, cal = make_calendar("birthday@example.com", "Birthdays")
    auth.post(
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
    [occurrence] = _events(auth, cal["id"], "2022-01-01T00:00:00Z", "2023-01-01T00:00:00Z")
    assert occurrence["recurrence_count"] == 2


def test_recurring_occurrence_overlapping_range_start_is_included(make_calendar):
    auth, cal = make_calendar("recur-span@example.com", "Spans")
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Two-day block",
            "start": "2026-09-01T09:00:00Z",
            "end": "2026-09-02T17:00:00Z",
            "rrule": "FREQ=DAILY",
        },
    )
    occurrences = _events(auth, cal["id"], "2026-09-10T00:00:00Z", "2026-09-10T12:00:00Z")
    # 09-09 09:00 -> 09-10 17:00 overlaps the window start; 09-10 starts inside it.
    assert [o["start"] for o in occurrences] == ["2026-09-09T09:00:00Z", "2026-09-10T09:00:00Z"]


def test_event_category_is_included_in_occurrences(make_calendar):
    auth, cal = make_calendar("categories@example.com", "Categories")
    category = auth.post(
        f"/api/calendars/{cal['id']}/categories",
        json={"name": "Birthday", "description": "Birthdays", "color": "#ec4899"},
    ).json()
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Birthday",
            "start": "2026-09-15T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
            "all_day": True,
            "category_id": category["id"],
        },
    )
    [occurrence] = _events(auth, cal["id"], "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z")
    assert occurrence["category_id"] == category["id"]
    assert occurrence["category_name"] == "Birthday"
    assert occurrence["category_color"] == "#ec4899"


def test_ical_feed_is_public_by_token(make_calendar, client):
    auth, cal = make_calendar("feedowner@example.com", "FeedCal")
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Public", "start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z"},
    )
    url = auth.get(f"/api/calendars/{cal['id']}/feed-url").json()["feed_url"]
    r = client.get(url)
    assert r.status_code == 200
    assert "VERSION:2.0" in r.text
    assert "SUMMARY:Public" in r.text
    assert client.get("/ics/not-a-token.ics").status_code == 404


def test_rotating_feed_token_invalidates_old_url(make_calendar, client):
    auth, cal = make_calendar("rotate@example.com", "Rotate")
    old = auth.get(f"/api/calendars/{cal['id']}/feed-url").json()["feed_url"]
    new = auth.post(f"/api/calendars/{cal['id']}/feed-token/rotate").json()["feed_url"]
    assert old != new
    assert client.get(old).status_code == 404
    assert client.get(new).status_code == 200


def test_event_edit_updates_ical_feed(make_calendar):
    auth, cal = make_calendar("feed-edit@example.com", "Feed")
    event = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Old title", "start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z"},
    ).json()
    auth.patch(f"/api/calendars/events/{event['id']}", json={"title": "New title"})

    feed = _feed(auth, cal["id"])
    assert "SUMMARY:New title" in feed
    assert "Old title" not in feed


def test_feed_excludes_pending_bookings(make_calendar):
    auth, cal = make_calendar("feed-pending@example.com", "Feed")
    resource = auth.post(
        f"/api/calendars/{cal['id']}/resources",
        json={"name": "Room", "requires_approval": True},
    ).json()
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={
            "title": "Pending booking",
            "start": "2026-10-01T10:00:00Z",
            "end": "2026-10-01T11:00:00Z",
            "resource_id": resource["id"],
        },
    )
    auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Confirmed event", "start": "2026-10-02T10:00:00Z", "end": "2026-10-02T11:00:00Z"},
    )

    feed = _feed(auth, cal["id"])
    assert "Confirmed event" in feed
    assert "Pending booking" not in feed


def test_event_title_and_description_optional(make_calendar):
    auth, cal = make_calendar("optional@example.com", "Optional")
    r = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z"},
    )
    assert r.status_code == 201
    event = r.json()
    assert event["title"] == ""
    assert event["description"] is None

    r = auth.patch(
        f"/api/calendars/events/{event['id']}",
        json={"title": "Has title", "description": "A description"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Has title"
    assert r.json()["description"] == "A description"

    r = auth.patch(
        f"/api/calendars/events/{event['id']}",
        json={"title": "", "description": None},
    )
    assert r.status_code == 200
    assert r.json()["title"] == ""
    assert r.json()["description"] is None


def _create_event(auth, cal_id):
    r = auth.post(
        f"/api/calendars/{cal_id}/events",
        json={"title": "Meeting", "start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z"},
    )
    assert r.status_code == 201
    return r.json()


def test_list_event_participants_empty(make_calendar):
    auth, cal = make_calendar("ep-empty@example.com", "Team")
    event = _create_event(auth, cal["id"])
    r = auth.get(f"/api/calendars/events/{event['id']}/participants")
    assert r.status_code == 200
    assert r.json() == []


def test_add_and_remove_external_participant(make_calendar):
    auth, cal = make_calendar("ep-ext@example.com", "Team")
    event = _create_event(auth, cal["id"])
    r = auth.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "External@Example.com", "status": "tentative"},
    )
    assert r.status_code == 201
    p = r.json()
    assert p["email"] == "external@example.com"
    assert p["user_id"] is None
    assert p["status"] == "tentative"

    r = auth.get(f"/api/calendars/events/{event['id']}/participants")
    assert len(r.json()) == 1

    r = auth.delete(f"/api/calendars/events/{event['id']}/participants/{p['id']}")
    assert r.status_code == 204
    assert auth.get(f"/api/calendars/events/{event['id']}/participants").json() == []


def test_add_participant_links_registered_user(make_calendar, user_factory, login, db):
    owner, cal = make_calendar("ep-reg@example.com", "Team")
    event = _create_event(owner, cal["id"])
    invitee = user_factory("ep-invitee@example.com", display_name="Invitee")

    r = owner.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "EP-INVITEE@EXAMPLE.COM"},
    )
    assert r.status_code == 201
    p = r.json()
    assert p["email"] == "ep-invitee@example.com"
    assert p["user_id"] == invitee["id"]
    assert p["display_name"] == "Invitee"
    assert p["status"] == "needs_action"

    # The invitee should have a notification
    from app.models import Notification
    notifications = db.query(Notification).filter(Notification.user_id == invitee["id"]).all()
    assert len(notifications) == 1
    assert notifications[0].type == "participant_added"


def test_cannot_add_duplicate_participant(make_calendar, user_factory):
    owner, cal = make_calendar("ep-dup@example.com", "Team")
    event = _create_event(owner, cal["id"])
    user_factory("ep-dup-user@example.com")
    owner.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "ep-dup-user@example.com"},
    )
    r = owner.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "EP-DUP-USER@EXAMPLE.COM"},
    )
    assert r.status_code == 400


def test_participant_status_update_by_organizer_and_self(make_calendar, user_factory, login, add_member):
    owner, cal = make_calendar("ep-status@example.com", "Team")
    event = _create_event(owner, cal["id"])
    invitee_info = user_factory("ep-status-user@example.com")
    add_member(owner, cal["id"], "ep-viewer@example.com", "viewer")
    invitee = login("ep-status-user@example.com")

    p = owner.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "ep-status-user@example.com"},
    ).json()

    # Organizer can update status
    r = owner.patch(
        f"/api/calendars/events/{event['id']}/participants/{p['id']}",
        json={"status": "accepted"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # Participant can update own status
    r = invitee.patch(
        f"/api/calendars/events/{event['id']}/participants/{p['id']}",
        json={"status": "declined"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "declined"

    # Viewer cannot update
    viewer = login("ep-viewer@example.com")
    r = viewer.patch(
        f"/api/calendars/events/{event['id']}/participants/{p['id']}",
        json={"status": "tentative"},
    )
    assert r.status_code == 403


def test_viewer_cannot_add_participant(make_calendar, add_member):
    owner, cal = make_calendar("ep-perm@example.com", "Team")
    event = _create_event(owner, cal["id"])
    viewer = add_member(owner, cal["id"], "ep-perm-viewer@example.com", "viewer")
    r = viewer.post(
        f"/api/calendars/events/{event['id']}/participants",
        json={"email": "someone@example.com"},
    )
    assert r.status_code == 403
