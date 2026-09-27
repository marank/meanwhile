import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def admin_client_session():
    original_admin_email = settings.admin_email
    settings.admin_email = "admin@example.com"
    client = TestClient(app)
    r = client.post(
        "/api/auth/register",
        json={"email": "admin@example.com", "display_name": "Admin", "password": "password123"},
    )
    if r.status_code == 400:
        r = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
    token = r.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    settings.admin_email = original_admin_email


@pytest.fixture
def admin_client(admin_client_session):
    return admin_client_session


def test_first_user_is_admin(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "display_name": "First", "password": "password123"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]

    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["is_admin"] is True
    assert r.json()["is_active"] is True


def test_admin_can_manage_app_settings(admin_client):
    r = admin_client.get("/api/admin/settings")
    assert r.status_code == 200
    settings = r.json()
    assert settings["app_name"] == "Calendar"

    r = admin_client.patch("/api/admin/settings", json={"app_name": "My Calendar"})
    assert r.status_code == 200
    assert r.json()["app_name"] == "My Calendar"


def test_non_admin_cannot_access_admin(admin_client, user_factory, client):
    user_factory("user@example.com")
    auth = TestClient(app)
    login = auth.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    auth.headers.update({"Authorization": f"Bearer {token}"})

    r = auth.get("/api/admin/settings")
    assert r.status_code == 403

    r = auth.get("/api/admin/users")
    assert r.status_code == 403


def test_admin_can_crud_users(admin_client):
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
    assert r.status_code == 200
    assert any(u["id"] == user_id for u in r.json())

    r = admin_client.patch(f"/api/admin/users/{user_id}", json={"display_name": "Updated"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Updated"

    r = admin_client.delete(f"/api/admin/users/{user_id}")
    assert r.status_code == 200

    r = admin_client.get("/api/admin/users")
    assert not any(u["email"] == "new@example.com" for u in r.json())


def test_admin_cannot_delete_self(admin_client):
    me = admin_client.get("/api/users/me").json()
    r = admin_client.delete(f"/api/admin/users/{me['id']}")
    assert r.status_code == 400
