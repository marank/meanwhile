"""
Tests for the per-user settings of the calendar overview ("All calendars" and folders).
"""

from typing import Any

import pytest

from apps.core.models import OverviewSettings, get_or_create_app_settings
from apps.core.models.calendar_colors import APP_COLORS
from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


def test_overview_starts_with_app_defaults_and_the_app_colors() -> None:
    app_settings = get_or_create_app_settings()
    app_settings.default_first_weekday = 1
    app_settings.default_show_week_numbers = True
    app_settings.save()

    settings = Api(make_user("owner")).get("/users/me/settings").json()
    assert settings["first_weekday"] == 1
    assert settings["show_week_numbers"] is True
    assert settings["use_calendar_colors"] is True
    assert {field: settings[field] for field in APP_COLORS} == APP_COLORS


def test_overview_settings_are_saved_per_user() -> None:
    owner = Api(make_user("owner"))
    other = Api(make_user("other"))
    res = owner.patch(
        "/users/me/settings",
        {
            "use_calendar_colors": False,
            "event_color": "#123456",
            "weekend_days": [6, 0, 6],
        },
    )
    assert res.status_code == 200, res.content
    assert res.json()["weekend_days"] == [0, 6]

    assert owner.get("/users/me/settings").json()["event_color"] == "#123456"
    assert other.get("/users/me/settings").json()["use_calendar_colors"] is True


def test_overview_colors_are_validated() -> None:
    res = Api(make_user("owner")).patch("/users/me/settings", {"base_color": "blue"})
    assert res.status_code == 422


def set_app_defaults(**values: Any) -> None:
    app_settings = get_or_create_app_settings()
    for field, value in values.items():
        setattr(app_settings, f"default_{field}", value)
    app_settings.save()


def test_the_week_layout_follows_app_defaults_changed_later() -> None:
    """Settings created before an admin changes the defaults (e.g. the admin's own) follow them."""
    owner = Api(make_user("owner"))
    assert owner.get("/users/me/settings").json()["first_weekday"] == 1  # Monday
    assert owner.patch("/users/me/settings", {"event_color": "#123456"}).status_code == 200

    set_app_defaults(first_weekday=0, weekend_days=[5, 6])

    settings = owner.get("/users/me/settings").json()
    assert settings["first_weekday"] == 0
    assert settings["weekend_days"] == [5, 6]


def test_a_layout_value_the_user_set_stays_theirs() -> None:
    owner = Api(make_user("owner"))
    assert owner.patch("/users/me/settings", {"first_weekday": 1}).status_code == 200

    set_app_defaults(first_weekday=0, show_week_numbers=True)

    settings = owner.get("/users/me/settings").json()
    assert settings["first_weekday"] == 1
    assert settings["show_week_numbers"] is True


def test_null_puts_a_layout_value_back_to_the_app_default() -> None:
    owner = Api(make_user("owner"))
    owner.patch("/users/me/settings", {"first_weekday": 3})
    set_app_defaults(first_weekday=1)

    res = owner.patch("/users/me/settings", {"first_weekday": None, "event_color": None})
    assert res.status_code == 200, res.content
    assert res.json()["first_weekday"] == 1
    assert res.json()["event_color"] == APP_COLORS["event_color"]


def test_reading_the_settings_stores_nothing() -> None:
    owner = Api(make_user("owner"))
    assert owner.get("/users/me/settings").status_code == 200
    assert not OverviewSettings.objects.exists()

    assert owner.patch("/users/me/settings", {"show_weekends": False}).status_code == 200
    stored = OverviewSettings.objects.get()
    assert stored.show_weekends is False
    assert stored.first_weekday is None
