import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"

from app import database  # noqa: E402
from app.api.auth import _login_failures  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Give every test its own empty in-memory database.

    The app (REST and CalDAV) resolves sessions through app.database, so
    swapping the module-level engine isolates every code path.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(
        database,
        "_SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_global_state(monkeypatch):
    _login_failures.clear()
    monkeypatch.setattr(settings, "admin_email", None)
    monkeypatch.setattr(settings, "base_url", None)
    yield
    _login_failures.clear()


@pytest.fixture
def db(isolated_db):
    session = database.get_session_local()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def login():
    """Return a new TestClient authenticated as *email*."""

    def _login(email: str, password: str = PASSWORD) -> TestClient:
        c = TestClient(app)
        resp = c.post("/api/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        c.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
        return c

    return _login


@pytest.fixture
def user_factory(client):
    """Register a user and return ``{"id", "email", "is_admin"}``.

    The first user registered in a test becomes admin (app behaviour).
    """

    def _make(email: str, password: str = PASSWORD, display_name: str = "User") -> dict:
        resp = client.post(
            "/api/auth/register",
            json={"email": email, "display_name": display_name, "password": password},
        )
        assert resp.status_code == 201, resp.text
        me = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
        ).json()
        return {"id": me["id"], "email": me["email"], "is_admin": me["is_admin"]}

    return _make


@pytest.fixture
def admin_client(user_factory, login):
    user = user_factory("admin@example.com", display_name="Admin")
    assert user["is_admin"]
    return login("admin@example.com")


@pytest.fixture
def make_calendar(user_factory, login):
    """Register *owner_email*, create a calendar, return (client, calendar)."""

    def _make(owner_email: str, name: str = "Team"):
        user_factory(owner_email)
        auth = login(owner_email)
        resp = auth.post("/api/calendars", json={"name": name, "color": "#000000"})
        assert resp.status_code == 201, resp.text
        return auth, resp.json()

    return _make


@pytest.fixture
def add_member(user_factory, login):
    """Register *email*, add them to the calendar with *role*, return their client."""

    def _add(owner_client: TestClient, calendar_id: str, email: str, role: str) -> TestClient:
        user = user_factory(email)
        resp = owner_client.post(
            f"/api/calendars/{calendar_id}/members",
            json={"user_id": user["id"], "role": role},
        )
        assert resp.status_code == 201, resp.text
        return login(email)

    return _add


BASE_DATE = datetime(2026, 10, 5, tzinfo=timezone.utc)


@pytest.fixture
def at():
    """Deterministic datetimes relative to a fixed Monday, 2026-10-05 UTC."""

    def _at(days: int = 0, hour: int = 10, minute: int = 0) -> datetime:
        return BASE_DATE + timedelta(days=days, hours=hour, minutes=minute)

    return _at
