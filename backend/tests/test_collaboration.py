def _event(auth, cal_id, title="Meet", **extra):
    body = {
        "title": title,
        "start": "2026-10-05T09:00:00Z",
        "end": "2026-10-05T10:00:00Z",
        **extra,
    }
    r = auth.post(f"/api/calendars/{cal_id}/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _notes(client):
    return [
        n for n in client.get("/api/notifications").json()
        if n["type"] != "member_added"
    ]


def _resource(auth, cal_id, name="Room", requires_approval=True):
    r = auth.post(
        f"/api/calendars/{cal_id}/resources",
        json={"name": name, "requires_approval": requires_approval},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Week numbers
# ---------------------------------------------------------------------------


def test_week_numbers_default_from_app_settings(admin_client):
    r = admin_client.patch(
        "/api/admin/settings", json={"default_show_week_numbers": True}
    )
    assert r.status_code == 200, r.text
    assert r.json()["default_show_week_numbers"] is True

    r = admin_client.post("/api/calendars", json={"name": "Team"})
    assert r.status_code == 201, r.text
    assert r.json()["show_week_numbers"] is True

    r = admin_client.post(
        "/api/calendars", json={"name": "Other", "show_week_numbers": False}
    )
    assert r.status_code == 201, r.text
    assert r.json()["show_week_numbers"] is False


def test_week_numbers_update_via_patch(make_calendar):
    auth, cal = make_calendar("weeknum@example.com")
    assert cal["show_week_numbers"] is False
    r = auth.patch(
        f"/api/calendars/{cal['id']}", json={"show_week_numbers": True}
    )
    assert r.status_code == 200, r.text
    assert r.json()["show_week_numbers"] is True


# ---------------------------------------------------------------------------
# User date/time format preferences
# ---------------------------------------------------------------------------


def test_user_format_prefs_persist(user_factory, login):
    user_factory("prefs@example.com")
    auth = login("prefs@example.com")
    me = auth.get("/api/users/me").json()
    assert me["time_format"] == "auto"
    assert me["date_format"] == "auto"

    r = auth.patch(
        "/api/users/me", json={"time_format": "12h", "date_format": "mdy"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["time_format"] == "12h"
    assert r.json()["date_format"] == "mdy"
    assert auth.get("/api/users/me").json()["date_format"] == "mdy"


def test_user_format_prefs_invalid(user_factory, login):
    user_factory("prefs2@example.com")
    auth = login("prefs2@example.com")
    assert (
        auth.patch("/api/users/me", json={"time_format": "31h"}).status_code
        == 422
    )
    assert (
        auth.patch("/api/users/me", json={"date_format": "xyz"}).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# Occurrence flags
# ---------------------------------------------------------------------------


def test_occurrence_can_edit_and_is_recurring(make_calendar, add_member, at):
    auth, cal = make_calendar("occedit@example.com")
    contributor = add_member(auth, cal["id"], "occ-contrib@example.com", "contributor")

    mine = _event(contributor, cal["id"], "Mine")
    theirs = _event(auth, cal["id"], "Theirs")
    recurring = _event(auth, cal["id"], "Weekly", rrule="FREQ=WEEKLY")

    start, end = at(-2).isoformat(), at(30).isoformat()

    def flags(client):
        occs = client.get(
            f"/api/calendars/{cal['id']}/events",
            params={"start": start, "end": end},
        ).json()
        return {o["event_id"]: o for o in occs}

    contrib_view = flags(contributor)
    assert contrib_view[mine["id"]]["can_edit"] is True
    assert contrib_view[theirs["id"]]["can_edit"] is False
    assert contrib_view[recurring["id"]]["is_recurring"] is True
    assert contrib_view[mine["id"]]["is_recurring"] is False

    owner_view = flags(auth)
    assert owner_view[theirs["id"]]["can_edit"] is True
    assert owner_view[mine["id"]]["can_edit"] is True


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def test_comments_permissions(make_calendar, add_member):
    auth, cal = make_calendar("cmt-owner@example.com")
    contributor = add_member(auth, cal["id"], "cmt-contrib@example.com", "contributor")
    other = add_member(auth, cal["id"], "cmt-other@example.com", "contributor")
    viewer = add_member(auth, cal["id"], "cmt-viewer@example.com", "viewer")
    editor = add_member(auth, cal["id"], "cmt-editor@example.com", "editor")
    event = _event(auth, cal["id"])

    r = contributor.post(
        f"/api/calendars/events/{event['id']}/comments", json={"body": " hi "}
    )
    assert r.status_code == 201, r.text
    comment = r.json()
    assert comment["body"] == "hi"
    assert comment["author_name"] == "User"

    assert (
        viewer.post(
            f"/api/calendars/events/{event['id']}/comments",
            json={"body": "nope"},
        ).status_code
        == 403
    )
    assert (
        contributor.post(
            f"/api/calendars/events/{event['id']}/comments",
            json={"body": "   "},
        ).status_code
        == 422
    )

    # Author and editors may delete; other contributors may not.
    assert (
        other.delete(
            f"/api/calendars/events/comments/{comment['id']}"
        ).status_code
        == 403
    )
    r = contributor.post(
        f"/api/calendars/events/{event['id']}/comments",
        json={"body": "to delete"},
    )
    victim = r.json()["id"]
    assert (
        contributor.delete(
            f"/api/calendars/events/comments/{victim}"
        ).status_code
        == 204
    )
    assert (
        editor.delete(
            f"/api/calendars/events/comments/{comment['id']}"
        ).status_code
        == 204
    )
    assert (
        viewer.get(f"/api/calendars/events/{event['id']}/comments").json()
        == []
    )


def test_comments_hidden_for_cancelled_event(make_calendar, add_member):
    auth, cal = make_calendar("cmt-hidden@example.com")
    viewer = add_member(auth, cal["id"], "cmt-h-viewer@example.com", "contributor")
    event = _event(auth, cal["id"])
    auth.post(f"/api/events/{event['id']}/cancel", json={})

    assert (
        viewer.get(f"/api/calendars/events/{event['id']}/comments").status_code
        == 404
    )
    # The creator can still see them.
    assert (
        auth.get(f"/api/calendars/events/{event['id']}/comments").status_code
        == 200
    )


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


def test_activity_recorded(make_calendar, add_member):
    auth, cal = make_calendar("act-owner@example.com")
    approver = add_member(auth, cal["id"], "act-approver@example.com", "editor")
    approver_id = approver.get("/api/users/me").json()["id"]
    room = _resource(auth, cal["id"])
    auth.post(
        f"/api/resources/{room['id']}/approvers", json={"user_id": approver_id}
    )

    event = _event(auth, cal["id"])
    activity = auth.get(f"/api/calendars/events/{event['id']}/activity").json()
    assert [a["action"] for a in activity] == ["created"]

    # No-op patch records nothing.
    auth.patch(f"/api/calendars/events/{event['id']}", json={"title": event["title"]})
    activity = auth.get(f"/api/calendars/events/{event['id']}/activity").json()
    assert [a["action"] for a in activity] == ["created"]

    r = auth.patch(
        f"/api/calendars/events/{event['id']}",
        json={"title": "New", "start": "2026-10-06T09:00:00Z", "end": "2026-10-06T10:00:00Z"},
    )
    assert r.status_code == 200, r.text
    activity = auth.get(f"/api/calendars/events/{event['id']}/activity").json()
    assert [a["action"] for a in activity] == ["created", "updated"]
    assert activity[1]["details"]["fields"] == ["title", "start", "end"]

    # Booking an approval-gated resource flips the status back to pending.
    r = auth.patch(
        f"/api/calendars/events/{event['id']}",
        json={"resource_id": room["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    activity = auth.get(f"/api/calendars/events/{event['id']}/activity").json()
    assert activity[2]["details"]["fields"] == ["resource"]
    assert activity[2]["details"]["status"] == "pending"

    approver.post(f"/api/events/{event['id']}/approve", json={})
    activity = auth.get(f"/api/calendars/events/{event['id']}/activity").json()
    assert [a["action"] for a in activity] == ["created", "updated", "updated", "approved"]
    assert activity[3]["actor_name"] == "User"


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def test_approval_requested_notifies_approver_not_actor(make_calendar, add_member):
    auth, cal = make_calendar("ntf-owner@example.com")
    approver = add_member(auth, cal["id"], "ntf-approver@example.com", "editor")
    booker = add_member(auth, cal["id"], "ntf-booker@example.com", "contributor")
    approver_id = approver.get("/api/users/me").json()["id"]
    room = _resource(auth, cal["id"])
    auth.post(
        f"/api/resources/{room['id']}/approvers", json={"user_id": approver_id}
    )

    event = _event(booker, cal["id"], resource_id=room["id"])
    assert event["status"] == "pending"

    notes = _notes(approver)
    assert [n["type"] for n in notes] == ["approval_requested"]
    assert notes[0]["event_id"] == event["id"]
    # The actor is never notified about their own action.
    assert _notes(booker) == []
    # The owner is always a recipient too.
    owner_notes = auth.get("/api/notifications").json()
    assert [n["type"] for n in owner_notes] == ["approval_requested"]


def test_approve_notifies_creator(make_calendar, add_member):
    auth, cal = make_calendar("ntf2-owner@example.com")
    booker = add_member(auth, cal["id"], "ntf2-booker@example.com", "contributor")
    room = _resource(auth, cal["id"])
    event = _event(booker, cal["id"], resource_id=room["id"])

    auth.post(f"/api/events/{event['id']}/approve", json={"note": "go"})
    notes = _notes(booker)
    assert [n["type"] for n in notes] == ["booking_approved"]
    assert notes[0]["data"] == {"note": "go"}
    assert notes[0]["title"] == "Meet"


def test_member_added_notification(make_calendar, add_member):
    auth, cal = make_calendar("ntf3-owner@example.com")
    member = add_member(auth, cal["id"], "ntf3-member@example.com", "viewer")
    notes = member.get("/api/notifications").json()
    assert [n["type"] for n in notes] == ["member_added"]
    assert notes[0]["title"] == cal["name"]
    assert notes[0]["data"] == {"role": "viewer"}


def test_comment_added_notifies_creator_and_commenters(make_calendar, add_member):
    auth, cal = make_calendar("ntf4-owner@example.com")
    contributor = add_member(
        auth, cal["id"], "ntf4-contrib@example.com", "contributor"
    )
    event = _event(auth, cal["id"])

    contributor.post(
        f"/api/calendars/events/{event['id']}/comments", json={"body": "hi"}
    )
    notes = auth.get("/api/notifications").json()
    assert [n["type"] for n in notes] == ["comment_added"]
    assert notes[0]["event_id"] == event["id"]

    # A reply from the creator notifies the earlier commenter.
    auth.post(
        f"/api/calendars/events/{event['id']}/comments", json={"body": "thanks"}
    )
    notes = _notes(contributor)
    assert [n["type"] for n in notes] == ["comment_added"]


def test_notification_read_flow(make_calendar, add_member, user_factory, login):
    auth, cal = make_calendar("ntf5-owner@example.com")
    outsider = user_factory("ntf5-outsider@example.com")
    outsider_client = login("ntf5-outsider@example.com")
    member = add_member(auth, cal["id"], "ntf5-member@example.com", "viewer")

    assert member.get("/api/notifications/unread-count").json() == {"count": 1}
    note = member.get("/api/notifications").json()[0]

    r = member.post(f"/api/notifications/{note['id']}/read")
    assert r.status_code == 200, r.text
    assert r.json()["read_at"] is not None
    assert member.get("/api/notifications/unread-count").json() == {"count": 0}

    # Cannot touch another user's notification.
    assert (
        outsider_client.post(f"/api/notifications/{note['id']}/read").status_code
        == 404
    )
    assert outsider["id"] != ""

    # read-all clears everything.
    add_member(auth, cal["id"], "ntf5-m2@example.com", "viewer")
    m2 = login("ntf5-m2@example.com")
    assert m2.get("/api/notifications/unread-count").json() == {"count": 1}
    m2.post("/api/notifications/read-all")
    assert m2.get("/api/notifications/unread-count").json() == {"count": 0}
