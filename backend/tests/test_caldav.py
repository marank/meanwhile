import base64

import pytest

EMAIL = "caldav@example.com"


def _basic(email: str = EMAIL, password: str = "password123") -> dict:
    creds = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def _ics(uid: str, summary: str, extra: str = "") -> str:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test Client//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        "DTSTART:20261001T090000Z\r\n"
        "DTEND:20261001T100000Z\r\n"
        f"SUMMARY:{summary}\r\n"
        f"{extra}"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@pytest.fixture
def dav(make_calendar, client):
    """Return (rest_client, calendar, caldav_collection_url)."""
    auth, cal = make_calendar(EMAIL, "CalDAV Test")
    return auth, cal, f"/caldav/{EMAIL}/{cal['id']}/"


def _put(client, url, ics):
    r = client.request(
        "PUT", url, content=ics, headers={**_basic(), "Content-Type": "text/calendar"}
    )
    assert r.status_code in (201, 204), r.text


def _only_event_id(auth, cal_id):
    occurrences = auth.get(
        f"/api/calendars/{cal_id}/events",
        params={"start": "2026-09-01T00:00:00Z", "end": "2026-11-01T00:00:00Z"},
    ).json()
    assert len(occurrences) == 1
    return occurrences[0]["event_id"]


def test_propfind_root_requires_auth(client, dav):
    assert client.request("PROPFIND", "/caldav/").status_code == 401
    assert client.request("PROPFIND", "/caldav/", headers=_basic()).status_code == 207


def test_caldav_roundtrip(client, dav):
    auth, cal, coll = dav
    _put(client, f"{coll}u1.ics", _ics("u1", "CalDAV Meeting"))

    r = client.get(f"{coll}u1.ics", headers=_basic())
    assert r.status_code == 200
    assert "SUMMARY:CalDAV Meeting" in r.text

    # Visible through the REST API as well.
    event = auth.get(f"/api/calendars/events/{_only_event_id(auth, cal['id'])}").json()
    assert event["title"] == "CalDAV Meeting"
    assert event["uid"] == "u1"


def test_rest_created_event_is_served_via_caldav(client, dav):
    auth, cal, coll = dav
    event = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "From web", "start": "2026-10-01T09:00:00Z", "end": "2026-10-01T10:00:00Z"},
    ).json()

    r = client.get(f"{coll}{event['uid']}.ics", headers=_basic())
    assert r.status_code == 200, r.text
    assert r.text.startswith("BEGIN:VCALENDAR")
    assert "SUMMARY:From web" in r.text

    r = client.request("PROPFIND", coll, headers={**_basic(), "Depth": "1"})
    assert r.status_code == 207, r.text
    assert f"{event['uid']}.ics" in r.text


def test_rest_edit_is_reflected_via_caldav_and_keeps_client_properties(client, dav):
    auth, cal, coll = dav
    _put(client, f"{coll}u2.ics", _ics("u2", "Old", extra="X-CLIENT-PROP:keep-me\r\n"))

    event_id = _only_event_id(auth, cal["id"])
    r = auth.patch(f"/api/calendars/events/{event_id}", json={"title": "New"})
    assert r.status_code == 200

    r = client.get(f"{coll}u2.ics", headers=_basic())
    assert r.status_code == 200, r.text
    assert "SUMMARY:New" in r.text
    assert "SUMMARY:Old" not in r.text
    assert "X-CLIENT-PROP:keep-me" in r.text


def test_caldav_etag_is_stable_between_requests(client, dav):
    auth, cal, coll = dav
    event = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Stable", "start": "2026-10-01T09:00:00Z", "end": "2026-10-01T10:00:00Z"},
    ).json()

    first = client.get(f"{coll}{event['uid']}.ics", headers=_basic())
    second = client.get(f"{coll}{event['uid']}.ics", headers=_basic())
    assert first.headers["etag"] == second.headers["etag"]


def test_legacy_bare_vevent_rows_are_served(client, dav, db):
    from app.models import Event

    auth, cal, coll = dav
    event = auth.post(
        f"/api/calendars/{cal['id']}/events",
        json={"title": "Legacy", "start": "2026-10-01T09:00:00Z", "end": "2026-10-01T10:00:00Z"},
    ).json()
    # Rows written before the fix stored a VEVENT without a VCALENDAR wrapper.
    row = db.get(Event, event["id"])
    row.raw_ical = (
        "BEGIN:VEVENT\r\nUID:{0}\r\nSUMMARY:Legacy\r\n"
        "DTSTART:20261001T090000Z\r\nDTEND:20261001T100000Z\r\nEND:VEVENT\r\n"
    ).format(event["uid"])
    db.commit()

    r = client.get(f"{coll}{event['uid']}.ics", headers=_basic())
    assert r.status_code == 200, r.text
    assert "SUMMARY:Legacy" in r.text


def test_caldav_denies_non_members(client, dav, user_factory):
    _, _, coll = dav
    user_factory("stranger@example.com")
    r = client.request(
        "PROPFIND", coll, headers={**_basic("stranger@example.com"), "Depth": "1"}
    )
    assert r.status_code in (403, 404)
