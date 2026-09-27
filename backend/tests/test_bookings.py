def _resource(auth, cal_id, name="Car", requires_approval=True):
    r = auth.post(
        f"/api/calendars/{cal_id}/resources",
        json={"name": name, "requires_approval": requires_approval},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _book(auth, cal_id, resource_id, start, end, title="Trip"):
    return auth.post(
        f"/api/calendars/{cal_id}/events",
        json={"title": title, "start": start, "end": end, "resource_id": resource_id},
    )


def test_approved_booking_blocks_overlap(make_calendar, at):
    auth, cal = make_calendar("caradmin@example.com", "Cars")
    car = _resource(auth, cal["id"])
    start, end = at(1, hour=9).isoformat(), at(1, hour=17).isoformat()

    event = _book(auth, cal["id"], car["id"], start, end).json()
    assert event["status"] == "pending"

    r = auth.post(f"/api/events/{event['id']}/approve", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    assert _book(auth, cal["id"], car["id"], start, end, "Overlap").status_code == 409


def test_pending_booking_does_not_block(make_calendar, at):
    auth, cal = make_calendar("pending-block@example.com", "Cars")
    car = _resource(auth, cal["id"])
    start, end = at(1, hour=9).isoformat(), at(1, hour=17).isoformat()

    assert _book(auth, cal["id"], car["id"], start, end).status_code == 201
    assert _book(auth, cal["id"], car["id"], start, end, "Second").status_code == 201


def test_confirmed_booking_blocks_overlap(make_calendar, at):
    auth, cal = make_calendar("caradmin2@example.com", "Cars")
    car = _resource(auth, cal["id"], requires_approval=False)
    start, end = at(1, hour=9).isoformat(), at(1, hour=17).isoformat()

    r = _book(auth, cal["id"], car["id"], start, end)
    assert r.json()["status"] == "confirmed"
    assert _book(auth, cal["id"], car["id"], start, end, "Overlap").status_code == 409


def test_booking_conflict_inside_multi_day_booking(make_calendar, at):
    auth, cal = make_calendar("caradmin3@example.com", "Cars")
    car = _resource(auth, cal["id"])
    event = _book(auth, cal["id"], car["id"], at(1, hour=9).isoformat(), at(3, hour=17).isoformat()).json()
    auth.post(f"/api/events/{event['id']}/approve", json={})

    r = _book(auth, cal["id"], car["id"], at(2, hour=10).isoformat(), at(2, hour=12).isoformat(), "Mid")
    assert r.status_code == 409


def test_adjacent_bookings_do_not_conflict(make_calendar, at):
    auth, cal = make_calendar("adjacent@example.com", "Cars")
    car = _resource(auth, cal["id"], requires_approval=False)
    assert _book(auth, cal["id"], car["id"], at(1, hour=9).isoformat(), at(1, hour=12).isoformat()).status_code == 201
    assert _book(auth, cal["id"], car["id"], at(1, hour=12).isoformat(), at(1, hour=15).isoformat()).status_code == 201


def test_editing_booking_with_other_bookings_on_resource(make_calendar):
    auth, cal = make_calendar("naive-conflict@example.com", "Cars")
    car = _resource(auth, cal["id"], requires_approval=False)
    _book(auth, cal["id"], car["id"], "2026-10-01T09:00:00Z", "2026-10-01T10:00:00Z", "A")
    b = _book(auth, cal["id"], car["id"], "2026-10-02T09:00:00Z", "2026-10-02T10:00:00Z", "B").json()

    # Title-only edit reloads start/end from the DB.
    r = auth.patch(f"/api/calendars/events/{b['id']}", json={"title": "B2"})
    assert r.status_code == 200, r.text

    # Moving B onto A must still be detected as a conflict.
    r = auth.patch(
        f"/api/calendars/events/{b['id']}",
        json={"start": "2026-10-01T09:30:00Z", "end": "2026-10-01T10:30:00Z"},
    )
    assert r.status_code == 409


def test_resource_approver_can_list_and_approve(make_calendar, add_member, user_factory):
    owner, cal = make_calendar("ap-owner@example.com", "Fleet")
    approver = add_member(owner, cal["id"], "ap-approver@example.com", "editor")
    booker = add_member(owner, cal["id"], "ap-booker@example.com", "contributor")
    approver_id = approver.get("/api/users/me").json()["id"]

    van = _resource(owner, cal["id"], "Van")
    r = owner.post(f"/api/resources/{van['id']}/approvers", json={"user_id": approver_id})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "ap-approver@example.com"

    event = _book(booker, cal["id"], van["id"], "2026-10-05T09:00:00Z", "2026-10-05T12:00:00Z").json()
    assert event["status"] == "pending"

    pending = approver.get("/api/approvals").json()
    assert [e["id"] for e in pending] == [event["id"]]
    assert [a["email"] for a in pending[0]["approver_pool"]] == ["ap-approver@example.com"]

    # The booker is not an approver.
    assert booker.get("/api/approvals").json() == []
    assert booker.post(f"/api/events/{event['id']}/approve", json={}).status_code == 403

    r = approver.post(f"/api/events/{event['id']}/approve", json={"note": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["decision_note"] == "ok"
    assert approver.get("/api/approvals").json() == []


def test_reject_booking(make_calendar):
    auth, cal = make_calendar("reject@example.com", "Fleet")
    van = _resource(auth, cal["id"], "Van")
    event = _book(auth, cal["id"], van["id"], "2026-10-05T09:00:00Z", "2026-10-05T12:00:00Z").json()

    r = auth.post(f"/api/events/{event['id']}/reject", json={"note": "busy"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    # Already decided.
    assert auth.post(f"/api/events/{event['id']}/approve", json={}).status_code == 400


def test_approval_datetimes_are_utc(make_calendar):
    auth, cal = make_calendar("approval-tz@example.com", "Rooms")
    room = _resource(auth, cal["id"], "Room")
    _book(auth, cal["id"], room["id"], "2026-10-01T09:00:00Z", "2026-10-01T10:00:00Z")

    [pending] = auth.get("/api/approvals").json()
    assert pending["start"] == "2026-10-01T09:00:00Z"
    assert pending["end"] == "2026-10-01T10:00:00Z"


def test_rescheduling_approved_booking_requires_reapproval(make_calendar):
    auth, cal = make_calendar("re-ap@example.com", "Fleet")
    van = _resource(auth, cal["id"], "Van")
    event = _book(auth, cal["id"], van["id"], "2026-10-05T09:00:00Z", "2026-10-05T12:00:00Z").json()
    auth.post(f"/api/events/{event['id']}/approve", json={})

    r = auth.patch(
        f"/api/calendars/events/{event['id']}",
        json={"start": "2026-10-06T09:00:00Z", "end": "2026-10-06T12:00:00Z"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["decided_by"] is None

    # Title-only edit must not reset the status.
    auth.post(f"/api/events/{event['id']}/approve", json={})
    r = auth.patch(f"/api/calendars/events/{event['id']}", json={"title": "Renamed"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_event_patch_can_clear_resource_with_null(make_calendar):
    auth, cal = make_calendar("clear-res@example.com", "Fleet")
    van = _resource(auth, cal["id"], "Van")
    event = _book(auth, cal["id"], van["id"], "2026-10-05T09:00:00Z", "2026-10-05T12:00:00Z").json()
    assert event["status"] == "pending"

    r = auth.patch(f"/api/calendars/events/{event['id']}", json={"resource_id": None})
    assert r.status_code == 200
    assert r.json()["resource_id"] is None
    assert r.json()["status"] == "confirmed"

    # Omitting resource_id leaves it unchanged.
    auth.patch(f"/api/calendars/events/{event['id']}", json={"resource_id": van["id"]})
    r = auth.patch(f"/api/calendars/events/{event['id']}", json={"title": "Still booked"})
    assert r.json()["resource_id"] == van["id"]
