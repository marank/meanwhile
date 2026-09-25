import base64
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


def _basic(email: str, password: str = "password123") -> str:
    creds = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {creds}"


def test_caldav_propfind_and_roundtrip(client, user_factory):
    user_factory("caldav@example.com")
    auth = TestClient(app)
    login = auth.post("/api/auth/login", json={"email": "caldav@example.com", "password": "password123"})
    token = login.json()["access_token"]
    auth.headers.update({"Authorization": f"Bearer {token}"})
    cal = auth.post("/api/calendars", json={"name": "CalDAV Test", "color": "#ff0000"}).json()

    # PROPFIND on root
    resp = client.request(
        "PROPFIND",
        "/caldav/",
        headers={"Authorization": _basic("caldav@example.com")},
    )
    assert resp.status_code == 207, resp.text

    # PUT event
    uid = "caldav-test-event-001"
    dtstart = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y%m%dT%H%M%SZ')
    dtend = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).strftime('%Y%m%dT%H%M%SZ')
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Calendar App//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:CalDAV Meeting\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    put = client.request(
        "PUT",
        f"/caldav/caldav@example.com/{cal['id']}/{uid}.ics",
        content=ics,
        headers={"Authorization": _basic("caldav@example.com"), "Content-Type": "text/calendar"},
    )
    assert put.status_code in (201, 204), put.text

    # GET event
    get = client.request(
        "GET",
        f"/caldav/caldav@example.com/{cal['id']}/{uid}.ics",
        headers={"Authorization": _basic("caldav@example.com")},
    )
    assert get.status_code == 200, get.text
    assert "CalDAV Meeting" in get.text
