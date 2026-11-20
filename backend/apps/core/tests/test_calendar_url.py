import pytest

from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


def test_calendar_url_path_can_be_set_and_cleared() -> None:
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()

    response = api.patch(f"/calendars/{calendar['id']}", {"url_path": "team-calendar"})
    assert response.status_code == 200, response.content
    assert response.json()["url_path"] == "team-calendar"

    response = api.patch(f"/calendars/{calendar['id']}", {"url_path": None})
    assert response.status_code == 200, response.content
    assert response.json()["url_path"] is None


def test_calendar_url_path_must_be_unique_and_readable() -> None:
    api = Api(make_user("owner"))
    first = api.post("/calendars", {"name": "First"}).json()
    second = api.post("/calendars", {"name": "Second"}).json()
    assert api.patch(f"/calendars/{first['id']}", {"url_path": "team-calendar"}).status_code == 200

    assert api.patch(f"/calendars/{second['id']}", {"url_path": "team-calendar"}).status_code == 409
    assert api.patch(f"/calendars/{second['id']}", {"url_path": "Not readable"}).status_code == 422
    assert api.patch(f"/calendars/{second['id']}", {"url_path": "folder"}).status_code == 422
    assert api.patch(f"/calendars/{second['id']}", {"url_path": "all"}).status_code == 422
