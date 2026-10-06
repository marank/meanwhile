def test_search_users_requires_two_characters_and_returns_dto(admin_client, user_factory):
    user_factory("alice@example.com", display_name="Alice")
    assert admin_client.get("/api/search", params={"entity": "users", "q": "a"}).json() == []

    r = admin_client.get("/api/search", params={"entity": "users", "q": "Ali"})
    assert r.status_code == 200
    assert r.json()[0] == {
        "id": r.json()[0]["id"],
        "type": "user",
        "label": "Alice",
        "subtitle": "alice@example.com",
        "meta": None,
    }


def test_search_groups_supports_empty_preload(admin_client):
    group = admin_client.post(
        "/api/groups", json={"name": "Engineering", "description": "Product team"}
    ).json()
    r = admin_client.get("/api/search", params={"entity": "groups"})
    assert r.status_code == 200
    assert r.json() == [{
        "id": group["id"], "type": "group", "label": "Engineering",
        "subtitle": "Product team", "meta": None,
    }]


def test_search_calendar_entities_and_access(make_calendar, add_member, user_factory, login):
    owner, calendar = make_calendar("search-owner@example.com")
    calendar_id = calendar["id"]
    resource = owner.post(
        f"/api/calendars/{calendar_id}/resources",
        json={"name": "Projector", "description": "Room A", "color": "#123456", "requires_approval": True},
    ).json()
    category = owner.post(
        f"/api/calendars/{calendar_id}/categories",
        json={"name": "Meeting", "color": "#654321"},
    ).json()

    resources = owner.get("/api/search", params={"entity": "resources", "calendar_id": calendar_id})
    assert resources.status_code == 200
    assert resources.json()[0] == {
        "id": resource["id"], "type": "resource", "label": "Projector",
        "subtitle": "Room A", "meta": {"requires_approval": True, "color": "#123456"},
    }
    categories = owner.get("/api/search", params={"entity": "categories", "calendar_id": calendar_id})
    assert categories.status_code == 200
    assert categories.json()[0] == {
        "id": category["id"], "type": "category", "label": "Meeting",
        "subtitle": None, "meta": {"color": "#654321"},
    }

    assert owner.get("/api/search", params={"entity": "resources"}).status_code == 422
    user_factory("search-outsider@example.com")
    outsider = login("search-outsider@example.com")
    assert outsider.get(
        "/api/search", params={"entity": "categories", "calendar_id": calendar_id}
    ).status_code == 403
