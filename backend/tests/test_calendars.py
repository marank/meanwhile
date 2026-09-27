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

    r = auth.get("/api/users/search", params={"q": "a_b"})
    assert [u["email"] for u in r.json()] == ["a_b@example.com"]


def test_feed_url_uses_configured_base_url(make_calendar, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "base_url", "https://cal.example.com/")
    auth, cal = make_calendar("base-url@example.com")
    url = auth.get(
        f"/api/calendars/{cal['id']}/feed-url", headers={"Host": "evil.example"}
    ).json()["feed_url"]
    assert url.startswith("https://cal.example.com/ics/")
