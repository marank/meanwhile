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
