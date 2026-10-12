"""
Tests for the per-user settings of the calendar overview ("All calendars" and folders).
"""

import pytest

from core.models import get_or_create_app_settings
from core.models.calendar_colors import APP_COLORS
from core.tests.test_approval_workflow import Api, make_user

pytestmark = pytest.mark.django_db


def test_overview_starts_with_app_defaults_and_the_app_colors():
    app_settings = get_or_create_app_settings()
    app_settings.default_first_weekday = 1
    app_settings.default_show_week_numbers = True
    app_settings.save()

    settings = Api(make_user("owner")).get("/users/me/settings").json()
    assert settings["first_weekday"] == 1
    assert settings["show_week_numbers"] is True
    assert settings["use_calendar_colors"] is True
    assert {field: settings[field] for field in APP_COLORS} == APP_COLORS


def test_overview_settings_are_saved_per_user():
    owner = Api(make_user("owner"))
    other = Api(make_user("other"))
    res = owner.patch("/users/me/settings", {
        "use_calendar_colors": False,
        "event_color": "#123456",
        "weekend_days": [6, 0, 6],
    })
    assert res.status_code == 200, res.content
    assert res.json()["weekend_days"] == [0, 6]

    assert owner.get("/users/me/settings").json()["event_color"] == "#123456"
    assert other.get("/users/me/settings").json()["use_calendar_colors"] is True


def test_overview_colors_are_validated():
    res = Api(make_user("owner")).patch("/users/me/settings", {"base_color": "blue"})
    assert res.status_code == 422
