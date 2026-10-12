"""
Tests for the stored calendar color roles.
"""

import importlib

import pytest

from core.models.calendar_colors import DEFAULT_COLORS
from core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db

migration = importlib.import_module("core.migrations.0003_calendar_color_roles")


def test_new_calendars_start_with_the_default_preset():
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    assert {field: calendar[field] for field in DEFAULT_COLORS} == DEFAULT_COLORS


def test_colors_can_be_set_individually():
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    res = api.patch(f"/calendars/{calendar['id']}", {"event_color": "#123456", "dark_border_color": "#abcdef"})
    assert res.status_code == 200, res.content
    assert res.json()["event_color"] == "#123456"
    assert res.json()["dark_border_color"] == "#abcdef"


def test_invalid_colors_are_rejected():
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    res = api.patch(f"/calendars/{calendar['id']}", {"event_color": "red"})
    assert res.status_code == 422


def test_occurrences_name_their_calendar():
    api = Api(make_user("owner"))
    calendar = api.post("/calendars", {"name": "Team"}).json()
    api.post(f"/calendars/{calendar['id']}/events", {
        "title": "Meeting", "start": "2030-01-07T09:00:00Z", "end": "2030-01-07T10:00:00Z",
    })
    occurrences = api.get(
        f"/calendars/{calendar['id']}/events?start=2030-01-01T00:00:00Z&end=2030-02-01T00:00:00Z"
    ).json()
    assert occurrences[0]["calendar_id"] == calendar["id"]
    assert "event_color" not in occurrences[0]


def test_migration_derives_the_default_preset_from_its_day_colors():
    # The derived colors of the default preset must come out of the same formulas the presets were made with.
    light = migration.derived_colors(DEFAULT_COLORS["base_color"], dark=False)
    dark = migration.derived_colors(DEFAULT_COLORS["dark_base_color"], dark=True)
    assert light == {
        "event": DEFAULT_COLORS["event_color"],
        "border": DEFAULT_COLORS["border_color"],
        "outer_border": DEFAULT_COLORS["outer_border_color"],
    }
    assert dark == {
        "event": DEFAULT_COLORS["dark_event_color"],
        "border": DEFAULT_COLORS["dark_border_color"],
        "outer_border": DEFAULT_COLORS["dark_outer_border_color"],
    }
