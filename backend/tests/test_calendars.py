from datetime import datetime, timezone


def test_create_and_list_calendars(make_calendar):
    auth, cal = make_calendar("owner@example.com", "Vacations")
    assert cal["name"] == "Vacations"

    r = auth.get("/api/calendars")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["calendar"]["id"] == cal["id"]
    assert data[0]["membership"]["role"] == "owner"


def test_new_calendar_uses_admin_defaults(admin_client):
    admin_client.patch(
        "/api/admin/settings",
        json={
            "default_first_weekday": 1,
            "default_show_weekends": False,
            "default_weekend_days": [5, 6],
        },
    )
    cal = admin_client.post("/api/calendars", json={"name": "Defaults"}).json()
    assert cal["first_weekday"] == 1
    assert cal["show_weekends"] is False
    assert cal["weekend_days"] == [5, 6]


def test_owner_can_update_display_settings(make_calendar):
    auth, cal = make_calendar("settings@example.com", "Settings")
    r = auth.patch(
        f"/api/calendars/{cal['id']}",
        json={
            "force_all_day": True,
            "first_weekday": 1,
            "show_weekends": False,
            "weekend_days": [5, 4, 4],
            "today_color": "#fef3c7",
            "dark_today_color": "#3f3f46",
        },
    )
    assert r.status_code == 200

    persisted = auth.get(f"/api/calendars/{cal['id']}").json()
    assert persisted["force_all_day"] is True
    assert persisted["first_weekday"] == 1
    assert persisted["show_weekends"] is False
    assert persisted["weekend_days"] == [4, 5]
    assert persisted["today_color"] == "#fef3c7"
    assert persisted["dark_today_color"] == "#3f3f46"


def test_member_management(make_calendar, user_factory, login):
    owner, cal = make_calendar("boss@example.com", "Team")
    member = user_factory("member@example.com")
    other = user_factory("other@example.com")
    members_url = f"/api/calendars/{cal['id']}/members"

    r = owner.post(members_url, json={"user_id": member["id"], "role": "contributor"})
    assert r.status_code == 201
    assert r.json()["role"] == "contributor"

    # Duplicates, invalid roles and a second owner are rejected.
    assert owner.post(members_url, json={"user_id": member["id"], "role": "viewer"}).status_code == 400
    assert owner.post(members_url, json={"user_id": other["id"], "role": "superuser"}).status_code == 422
    assert owner.post(members_url, json={"user_id": other["id"], "role": "owner"}).status_code == 400

    # Only the owner may manage members.
    member_client = login("member@example.com")
    assert member_client.post(members_url, json={"user_id": other["id"], "role": "viewer"}).status_code == 403

    r = owner.patch(f"{members_url}/{member['id']}", json={"role": "editor"})
    assert r.status_code == 200
    assert r.json()["role"] == "editor"

    assert owner.delete(f"{members_url}/{member['id']}").status_code == 204
    assert member_client.get(f"/api/calendars/{cal['id']}").status_code == 403


def test_non_member_is_forbidden(make_calendar, user_factory, login):
    _, cal = make_calendar("nm-owner@example.com", "Team")
    user_factory("nm-outsider@example.com")
    outsider = login("nm-outsider@example.com")

    assert outsider.get(f"/api/calendars/{cal['id']}").status_code == 403
    assert outsider.get(f"/api/calendars/{cal['id']}/members").status_code == 403
    assert outsider.delete(f"/api/calendars/{cal['id']}").status_code == 403


def test_missing_calendar_returns_404(user_factory, login):
    user_factory("nm-404@example.com")
    auth = login("nm-404@example.com")
    assert auth.get("/api/calendars/does-not-exist").status_code == 404


def test_user_search_treats_wildcards_literally(make_calendar, user_factory):
    auth, _ = make_calendar("searcher@example.com")
    user_factory("a_b@example.com")
    user_factory("axb@example.com")

    r = auth.get("/api/search", params={"entity": "users", "q": "a_b"})
    assert [u["subtitle"] for u in r.json()] == ["a_b@example.com"]


def test_owner_can_delete_calendar_with_members(make_calendar, user_factory):
    owner, cal = make_calendar("delete-owner@example.com", "Team")
    member = user_factory("delete-member@example.com")
    assert owner.post(
        f"/api/calendars/{cal['id']}/members",
        json={"user_id": member["id"], "role": "viewer"},
    ).status_code == 201

    assert owner.delete(f"/api/calendars/{cal['id']}").status_code == 204
    assert owner.get("/api/calendars").json() == []


def test_owner_can_delete_calendar_with_children(make_calendar, db):
    from app.models import Category, Event, Resource

    owner, cal = make_calendar("delete-children@example.com", "Team")
    cal_id = cal["id"]

    cat = owner.post(
        f"/api/calendars/{cal_id}/categories",
        json={"name": "Work", "color": "#000000"},
    )
    assert cat.status_code == 201

    res = owner.post(
        f"/api/calendars/{cal_id}/resources",
        json={"name": "Room A"},
    )
    assert res.status_code == 201
    resource_id = res.json()["id"]

    now = datetime.now(timezone.utc)
    event = owner.post(
        f"/api/calendars/{cal_id}/events",
        json={
            "title": "Standup",
            "start": now.isoformat(),
            "end": now.isoformat(),
            "all_day": True,
            "resource_id": resource_id,
        },
    )
    assert event.status_code == 201

    assert owner.delete(f"/api/calendars/{cal_id}").status_code == 204
    assert owner.get("/api/calendars").json() == []

    assert db.query(Category).filter(Category.calendar_id == cal_id).count() == 0
    assert db.query(Resource).filter(Resource.calendar_id == cal_id).count() == 0
    assert db.query(Event).filter(Event.calendar_id == cal_id).count() == 0


def test_feed_url_uses_configured_base_url(make_calendar, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "base_url", "https://cal.example.com/")
    auth, cal = make_calendar("base-url@example.com")
    url = auth.get(
        f"/api/calendars/{cal['id']}/feed-url", headers={"Host": "evil.example"}
    ).json()["feed_url"]
    assert url.startswith("https://cal.example.com/ics/")


# ---------------------------------------------------------------------------
# Public calendar tests
# ---------------------------------------------------------------------------


def test_owner_can_set_public_and_public_role(make_calendar):
    owner, cal = make_calendar("pub-owner@example.com", "Public Cal")
    # Default values
    assert cal["is_public"] is False
    assert cal["public_role"] == "viewer"

    # Set public with contributor role
    r = owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True, "public_role": "contributor"},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["is_public"] is True
    assert updated["public_role"] == "contributor"

    # Unset public
    r = owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": False},
    )
    assert r.status_code == 200
    assert r.json()["is_public"] is False


def test_non_owner_cannot_set_public(make_calendar, add_member):
    owner, cal = make_calendar("pub-no-owner@example.com", "Team")
    editor = add_member(owner, cal["id"], "pub-editor@example.com", "editor")

    r = editor.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True},
    )
    assert r.status_code == 403


def test_public_calendar_appears_in_other_user_list(make_calendar, user_factory, login):
    owner, cal = make_calendar("pub-list-owner@example.com", "Open Cal")
    owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True, "public_role": "viewer"},
    )

    user_factory("pub-list-other@example.com")
    other = login("pub-list-other@example.com")

    # The public calendar should appear in the other user's list
    r = other.get("/api/calendars")
    assert r.status_code == 200
    cals = r.json()
    ids = [c["calendar"]["id"] for c in cals]
    assert cal["id"] in ids
    match = [c for c in cals if c["calendar"]["id"] == cal["id"]][0]
    assert match["membership"]["role"] == "viewer"


def test_public_calendar_other_user_can_get(make_calendar, user_factory, login):
    owner, cal = make_calendar("pub-get-owner@example.com", "Open Cal")
    owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True, "public_role": "contributor"},
    )

    user_factory("pub-get-other@example.com")
    other = login("pub-get-other@example.com")

    r = other.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["is_public"] is True
    assert r.json()["my_membership"]["role"] == "contributor"


def test_direct_member_overrides_public_role(make_calendar, add_member):
    owner, cal = make_calendar("pub-override-owner@example.com", "Team")
    # Make calendar public with editor role
    owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True, "public_role": "editor"},
    )

    # Add a direct member as viewer (lower role than public)
    member = add_member(owner, cal["id"], "pub-override-member@example.com", "viewer")

    # Direct membership should win
    r = member.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["my_membership"]["role"] == "viewer"

    # Also check the calendar list
    cals = member.get("/api/calendars").json()
    match = [c for c in cals if c["calendar"]["id"] == cal["id"]][0]
    assert match["membership"]["role"] == "viewer"


def test_non_public_calendar_not_visible_to_outsider(make_calendar, user_factory, login):
    _, cal = make_calendar("nopub-owner@example.com", "Private")
    user_factory("nopub-other@example.com")
    other = login("nopub-other@example.com")

    r = other.get("/api/calendars")
    assert r.status_code == 200
    ids = [c["calendar"]["id"] for c in r.json()]
    assert cal["id"] not in ids

    r = other.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Group link tests
# ---------------------------------------------------------------------------


def test_group_link_gives_member_access(make_calendar, admin_client, user_factory, login):
    owner, cal = make_calendar("gl-owner@example.com", "Group Cal")

    # Create a group and add a user to it (admin API)
    group_resp = admin_client.post("/api/groups", json={"name": "Engineering"})
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    member_info = user_factory("gl-member@example.com")
    admin_client.post(f"/api/groups/{group_id}/members/{member_info['id']}")

    # Link the group to the calendar with editor role
    r = owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": group_id, "role": "editor"},
    )
    assert r.status_code == 201

    # The group member should now be able to access the calendar
    member_client = login("gl-member@example.com")
    r = member_client.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["my_membership"]["role"] == "editor"

    # Should appear in their calendar list
    cals = member_client.get("/api/calendars").json()
    ids = [c["calendar"]["id"] for c in cals]
    assert cal["id"] in ids
    match = [c for c in cals if c["calendar"]["id"] == cal["id"]][0]
    assert match["membership"]["role"] == "editor"


def test_group_link_non_member_no_access(make_calendar, admin_client, user_factory, login):
    owner, cal = make_calendar("gl-no-owner@example.com", "Group Cal")

    # Create a group (no members)
    group_resp = admin_client.post("/api/groups", json={"name": "Empty Group"})
    group_id = group_resp.json()["id"]

    owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": group_id, "role": "viewer"},
    )

    # A user NOT in the group should not see the calendar
    user_factory("gl-no-outsider@example.com")
    outsider = login("gl-no-outsider@example.com")

    r = outsider.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 403

    cals = outsider.get("/api/calendars").json()
    ids = [c["calendar"]["id"] for c in cals]
    assert cal["id"] not in ids


def test_direct_member_overrides_group_role(make_calendar, admin_client, user_factory, login):
    owner, cal = make_calendar("gl-dir-owner@example.com", "Team")

    # Create a group with editor link
    group_resp = admin_client.post("/api/groups", json={"name": "Devs"})
    group_id = group_resp.json()["id"]
    member_info = user_factory("gl-dir-member@example.com")
    admin_client.post(f"/api/groups/{group_id}/members/{member_info['id']}")
    owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": group_id, "role": "editor"},
    )

    # Add the user as direct viewer (overrides group editor)
    owner.post(
        f"/api/calendars/{cal['id']}/members",
        json={"user_id": member_info["id"], "role": "viewer"},
    )

    member_client = login("gl-dir-member@example.com")
    r = member_client.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["my_membership"]["role"] == "viewer"


def test_group_link_highest_role_wins(make_calendar, admin_client, user_factory, login):
    owner, cal = make_calendar("gl-multi-owner@example.com", "Team")

    # Create two groups
    g1 = admin_client.post("/api/groups", json={"name": "Group A"}).json()
    g2 = admin_client.post("/api/groups", json={"name": "Group B"}).json()

    member_info = user_factory("gl-multi-member@example.com")
    admin_client.post(f"/api/groups/{g1['id']}/members/{member_info['id']}")
    admin_client.post(f"/api/groups/{g2['id']}/members/{member_info['id']}")

    # Link groups with different roles
    owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": g1["id"], "role": "viewer"},
    )
    owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": g2["id"], "role": "editor"},
    )

    member_client = login("gl-multi-member@example.com")
    r = member_client.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["my_membership"]["role"] == "editor"  # highest wins


# ---------------------------------------------------------------------------
# Calendar group link CRUD tests
# ---------------------------------------------------------------------------


def test_group_link_crud(make_calendar, admin_client):
    owner, cal = make_calendar("crud-owner@example.com", "Team")

    # Create group
    group = admin_client.post("/api/groups", json={"name": "Ops"}).json()
    groups_url = f"/api/calendars/{cal['id']}/groups"

    # List (empty)
    r = owner.get(groups_url)
    assert r.status_code == 200
    assert r.json() == []

    # Create link
    r = owner.post(groups_url, json={"group_id": group["id"], "role": "viewer"})
    assert r.status_code == 201
    link = r.json()
    assert link["group"]["id"] == group["id"]
    assert link["group"]["name"] == "Ops"
    assert link["role"] == "viewer"
    link_id = link["id"]

    # Duplicate rejected
    r = owner.post(groups_url, json={"group_id": group["id"], "role": "editor"})
    assert r.status_code == 400

    # List (one link)
    r = owner.get(groups_url)
    assert len(r.json()) == 1

    # Update role
    r = owner.patch(f"{groups_url}/{link_id}", json={"role": "contributor"})
    assert r.status_code == 200
    assert r.json()["role"] == "contributor"

    # Delete
    r = owner.delete(f"{groups_url}/{link_id}")
    assert r.status_code == 204

    # Verify gone
    r = owner.get(groups_url)
    assert r.json() == []


def test_group_link_only_owner_can_manage(make_calendar, admin_client, add_member):
    owner, cal = make_calendar("gl-perm-owner@example.com", "Team")
    editor = add_member(owner, cal["id"], "gl-perm-editor@example.com", "editor")

    group = admin_client.post("/api/groups", json={"name": "Sales"}).json()
    groups_url = f"/api/calendars/{cal['id']}/groups"

    # Editor cannot list, create, update, or delete group links
    assert editor.get(groups_url).status_code == 403
    assert editor.post(groups_url, json={"group_id": group["id"], "role": "viewer"}).status_code == 403

    # Owner creates a link, editor cannot update or delete it
    link = owner.post(groups_url, json={"group_id": group["id"], "role": "viewer"}).json()
    assert editor.patch(f"{groups_url}/{link['id']}", json={"role": "editor"}).status_code == 403
    assert editor.delete(f"{groups_url}/{link['id']}").status_code == 403


def test_group_link_invalid_group_returns_404(make_calendar):
    owner, cal = make_calendar("gl-404-owner@example.com", "Team")
    r = owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": "nonexistent-id", "role": "viewer"},
    )
    assert r.status_code == 404


def test_deleting_calendar_deletes_group_links(make_calendar, admin_client, db):
    from app.models import CalendarGroup

    owner, cal = make_calendar("gl-del-owner@example.com", "Team")
    group = admin_client.post("/api/groups", json={"name": "QA"}).json()
    owner.post(
        f"/api/calendars/{cal['id']}/groups",
        json={"group_id": group["id"], "role": "viewer"},
    )

    assert db.query(CalendarGroup).filter(CalendarGroup.calendar_id == cal["id"]).count() == 1
    assert owner.delete(f"/api/calendars/{cal['id']}").status_code == 204
    assert db.query(CalendarGroup).filter(CalendarGroup.calendar_id == cal["id"]).count() == 0


def test_public_calendar_with_editor_role(make_calendar, user_factory, login):
    """A public calendar with editor role lets any user edit (via GET, the role is reported)."""
    owner, cal = make_calendar("pub-editor-owner@example.com", "Open Editor")
    owner.patch(
        f"/api/calendars/{cal['id']}",
        json={"is_public": True, "public_role": "editor"},
    )

    user_factory("pub-editor-other@example.com")
    other = login("pub-editor-other@example.com")

    r = other.get(f"/api/calendars/{cal['id']}")
    assert r.status_code == 200
    assert r.json()["my_membership"]["role"] == "editor"
