"""
Unknown ids are answered with 404, missing access with 403, never with a server error.
"""

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("method, path", [
    ("get", "/calendars/unknown"),
    ("get", "/calendars/unknown/members"),
    ("get", "/calendars/unknown/categories"),
    ("get", "/events/unknown"),
    ("patch", "/layout/folders/unknown"),
    ("delete", "/notifications/unknown"),
])
def test_unknown_ids_are_not_found(world, method, path):
    api = world["api"]["owner"]
    res = api.patch(path, {"name": "x"}) if method == "patch" else getattr(api, method)(path)
    assert res.status_code == 404
    assert res.json()["detail"].endswith("not found")


def test_not_found_names_what_is_missing(world):
    res = world["api"]["owner"].get("/calendars/unknown")
    assert res.json() == {"detail": "Calendar not found"}


def test_calendar_endpoints_tell_outsiders_and_lesser_roles_apart(world):
    cal_id = world["cal"]["id"]
    outsider, booker = world["api"]["outsider"], world["api"]["booker"]
    res = outsider.get(f"/calendars/{cal_id}/members")
    assert (res.status_code, res.json()["detail"]) == (403, "Not a member of this calendar")
    res = booker.post(f"/calendars/{cal_id}/members", {"user_id": str(world["users"]["outsider"].id), "role": "read"})
    assert (res.status_code, res.json()["detail"]) == (403, "Only who manages the calendar can add members")
    res = booker.post(f"/calendars/{cal_id}/categories", {"name": "Work"})
    assert (res.status_code, res.json()["detail"]) == (403, "Full access required")


def test_someone_without_access_cannot_delete_a_comment(world):
    owner = world["api"]["owner"]
    event = world["book"](owner, None).json()
    comment = owner.post(f"/events/{event['id']}/comments", {"body": "Hi"}).json()
    res = world["api"]["outsider"].delete(f"/events/{event['id']}/comments/{comment['id']}")
    assert res.status_code == 403


def test_only_public_endpoints_answer_without_a_session(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/rsvp/unknown-token").status_code == 404
    assert client.get("/api/calendars").status_code == 401
    assert client.get("/api/admin/users").status_code == 401


def test_roles_and_statuses_are_checked_by_the_schema(world):
    owner, cal = world["api"]["owner"], world["cal"]["id"]
    user_id = str(world["users"]["outsider"].id)
    assert owner.post(f"/calendars/{cal}/members", {"user_id": user_id, "role": "boss"}).status_code == 422
    event = world["book"](owner, None).json()
    res = owner.post(f"/events/{event['id']}/participants", {"email": "a@example.test", "status": "maybe"})
    assert res.status_code == 422
