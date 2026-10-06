def test_admin_can_manage_app_settings(admin_client):
    r = admin_client.get("/api/admin/settings")
    assert r.status_code == 200
    assert r.json()["app_name"] == "Calendar"

    r = admin_client.patch("/api/admin/settings", json={"app_name": "My Calendar"})
    assert r.status_code == 200
    assert r.json()["app_name"] == "My Calendar"

    r = admin_client.get("/api/admin/settings")
    assert r.json()["app_name"] == "My Calendar"


def test_public_settings_need_no_auth_and_reflect_admin_changes(admin_client, client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["app_name"] == "Calendar"

    admin_client.patch(
        "/api/admin/settings",
        json={"app_name": "Company Calendar", "default_first_weekday": 1},
    )

    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["app_name"] == "Company Calendar"
    assert r.json()["default_first_weekday"] == 1


def test_public_settings_cannot_be_modified(client):
    assert client.patch("/api/settings", json={"app_name": "Hacked"}).status_code == 405


def test_non_admin_cannot_access_admin(admin_client, user_factory, login):
    user_factory("user@example.com")
    user = login("user@example.com")

    assert user.get("/api/admin/settings").status_code == 403
    assert user.patch("/api/admin/settings", json={"app_name": "X"}).status_code == 403
    assert user.get("/api/admin/users").status_code == 403


def test_admin_can_crud_users(admin_client, client):
    r = admin_client.post(
        "/api/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New User",
            "password": "password123",
            "is_admin": False,
            "is_active": True,
        },
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    r = admin_client.get("/api/admin/users")
    assert any(u["id"] == user_id for u in r.json())

    r = admin_client.patch(f"/api/admin/users/{user_id}", json={"display_name": "Updated"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Updated"

    # Deactivated users can no longer log in.
    admin_client.patch(f"/api/admin/users/{user_id}", json={"is_active": False})
    r = client.post(
        "/api/auth/login", json={"email": "new@example.com", "password": "password123"}
    )
    assert r.status_code == 403

    r = admin_client.delete(f"/api/admin/users/{user_id}")
    assert r.status_code == 200
    r = admin_client.get("/api/admin/users")
    assert not any(u["id"] == user_id for u in r.json())


def test_admin_cannot_delete_self(admin_client):
    me = admin_client.get("/api/users/me").json()
    r = admin_client.delete(f"/api/admin/users/{me['id']}")
    assert r.status_code == 400


def test_admin_cannot_demote_or_deactivate_self(admin_client):
    me = admin_client.get("/api/users/me").json()

    assert admin_client.patch(
        f"/api/admin/users/{me['id']}", json={"is_admin": False}
    ).status_code == 400
    assert admin_client.patch(
        f"/api/admin/users/{me['id']}", json={"is_active": False}
    ).status_code == 400

    # Unrelated self-edits still work, and the account stays admin.
    r = admin_client.patch(
        f"/api/admin/users/{me['id']}", json={"display_name": "New name"}
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_admin_group_crud(admin_client):
    r = admin_client.post("/api/groups", json={"name": "Engineering", "description": "Eng team"})
    assert r.status_code == 201
    data = r.json()
    group_id = data["id"]
    assert data["name"] == "Engineering"
    assert data["description"] == "Eng team"
    assert data["member_count"] == 0
    assert data["members"] == []

    r = admin_client.get("/api/groups")
    assert r.status_code == 200
    groups = r.json()
    assert any(g["id"] == group_id for g in groups)
    assert groups[0]["member_count"] == 0

    r = admin_client.patch(f"/api/groups/{group_id}", json={"name": "Engineering 2"})
    assert r.status_code == 200
    assert r.json()["name"] == "Engineering 2"

    assert admin_client.delete(f"/api/groups/{group_id}").status_code == 204
    assert admin_client.get(f"/api/groups/{group_id}").status_code == 404


def test_non_admin_can_read_but_not_modify_groups(admin_client, user_factory, login):
    group = admin_client.post("/api/groups", json={"name": "Visible"}).json()
    user = user_factory("group-reader@example.com")
    auth = login("group-reader@example.com")

    assert auth.get("/api/groups").status_code == 200
    assert auth.get(f"/api/groups/{group['id']}").status_code == 200
    assert auth.post("/api/groups", json={"name": "Denied"}).status_code == 403
    assert auth.patch(f"/api/groups/{group['id']}", json={"name": "Denied"}).status_code == 403
    assert auth.delete(f"/api/groups/{group['id']}").status_code == 403
    assert auth.post(f"/api/groups/{group['id']}/members/{user['id']}").status_code == 403
    assert auth.delete(f"/api/groups/{group['id']}/members/{user['id']}").status_code == 403


def test_admin_group_members(admin_client, user_factory):
    g = admin_client.post("/api/groups", json={"name": "Members"}).json()
    gid = g["id"]
    u = user_factory("member@example.com", display_name="Member")

    r = admin_client.post(f"/api/groups/{gid}/members/{u['id']}")
    assert r.status_code == 200
    assert len(r.json()["members"]) == 1
    assert r.json()["members"][0]["email"] == "member@example.com"

    assert admin_client.post(f"/api/groups/{gid}/members/{u['id']}").status_code == 400

    assert admin_client.delete(f"/api/groups/{gid}/members/{u['id']}").status_code == 204
    r = admin_client.get(f"/api/groups/{gid}")
    assert r.json()["member_count"] == 0
    assert r.json()["members"] == []
    assert admin_client.delete(f"/api/groups/{gid}/members/{u['id']}").status_code == 404


def test_admin_create_user_with_group_ids(admin_client):
    g = admin_client.post("/api/groups", json={"name": "Admins"}).json()
    r = admin_client.post(
        "/api/admin/users",
        json={
            "email": "u1@example.com",
            "display_name": "U1",
            "password": "password123",
            "group_ids": [g["id"]],
        },
    )
    assert r.status_code == 201
    assert [gr["id"] for gr in r.json()["groups"]] == [g["id"]]
    assert admin_client.get(f"/api/groups/{g['id']}").json()["member_count"] == 1


def test_admin_update_user_group_ids_replaces_memberships(admin_client, user_factory):
    g1 = admin_client.post("/api/groups", json={"name": "G1"}).json()
    g2 = admin_client.post("/api/groups", json={"name": "G2"}).json()
    u = user_factory("u2@example.com", display_name="U2")

    r = admin_client.patch(f"/api/admin/users/{u['id']}", json={"group_ids": [g1["id"]]})
    assert r.status_code == 200
    assert {gr["id"] for gr in r.json()["groups"]} == {g1["id"]}

    r = admin_client.patch(f"/api/admin/users/{u['id']}", json={"group_ids": [g2["id"]]})
    assert r.status_code == 200
    assert {gr["id"] for gr in r.json()["groups"]} == {g2["id"]}

    r = admin_client.patch(f"/api/admin/users/{u['id']}", json={"group_ids": []})
    assert r.status_code == 200
    assert r.json()["groups"] == []


def test_admin_delete_group_removes_members_but_not_users(admin_client, user_factory):
    g = admin_client.post("/api/groups", json={"name": "Temp"}).json()
    u = user_factory("u3@example.com", display_name="U3")
    admin_client.post(f"/api/groups/{g['id']}/members/{u['id']}")

    assert admin_client.delete(f"/api/groups/{g['id']}").status_code == 204

    users = admin_client.get("/api/admin/users").json()
    assert any(x["id"] == u["id"] for x in users)
    assert admin_client.get(f"/api/groups/{g['id']}").status_code == 404
