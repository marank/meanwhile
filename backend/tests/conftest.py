import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CalendarMember, Role  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]


engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _get_db():
        return db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(client):
    def _make(email: str, password: str = "password123", display_name: str = "User"):
        resp = client.post(
            "/api/auth/register",
            json={"email": email, "display_name": display_name, "password": password},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make


@pytest.fixture
def auth_client_factory(client):
    def _make(email: str, password: str = "password123"):
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        original_headers = dict(client.headers)
        client.headers.update({"Authorization": f"Bearer {token}"})
        return client

    return _make


@pytest.fixture
def make_calendar(db, user_factory, client):
    def _make(owner_email: str, name: str = "Team", role_for_owner: str = Role.OWNER.value):
        user_factory(owner_email)
        auth = TestClient(app)
        login = auth.post(
            "/api/auth/login",
            json={"email": owner_email, "password": "password123"},
        )
        token = login.json()["access_token"]
        auth.headers.update({"Authorization": f"Bearer {token}"})
        resp = auth.post("/api/calendars", json={"name": name, "color": "#000000"})
        assert resp.status_code == 201, resp.text
        cal = resp.json()
        return auth, cal

    return _make


@pytest.fixture
def make_datetime():
    def _make(days: int = 0, hour: int = 10, minute: int = 0):
        return datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days)

    return _make
