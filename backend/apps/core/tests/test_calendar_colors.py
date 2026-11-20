"""
Tests for the stored calendar color roles.
"""

import pytest

from apps.core.models.calendar_colors import DEFAULT_COLORS
from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


def test_new_calendars_start_with_the_default_preset() -> None:
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    assert {field: calendar[field] for field in DEFAULT_COLORS} == DEFAULT_COLORS


def test_colors_can_be_set_individually() -> None:
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    res = api.patch(f"/calendars/{calendar['id']}", {"event_color": "#123456", "dark_border_color": "#abcdef"})
    assert res.status_code == 200, res.content
    assert res.json()["event_color"] == "#123456"
    assert res.json()["dark_border_color"] == "#abcdef"


def test_invalid_colors_are_rejected() -> None:
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    res = api.patch(f"/calendars/{calendar['id']}", {"event_color": "red"})
    assert res.status_code == 422


def test_occurrences_name_their_calendar() -> None:
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    api.post(
        f"/calendars/{calendar['id']}/events",
        {
            "title": "Meeting",
            "start": "2030-01-07T09:00:00Z",
            "end": "2030-01-07T10:00:00Z",
        },
    )
    occurrences = api.get(
        f"/calendars/{calendar['id']}/events?start=2030-01-01T00:00:00Z&end=2030-02-01T00:00:00Z"
    ).json()
    assert occurrences[0]["calendar_id"] == calendar["id"]
    assert "event_color" not in occurrences[0]
