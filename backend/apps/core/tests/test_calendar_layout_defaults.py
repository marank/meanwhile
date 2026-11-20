"""
A calendar's week layout follows the app's defaults until someone who manages it sets it, also
when an admin changes the defaults later.
"""

from typing import Any

import pytest

from apps.core.models import Calendar, get_or_create_app_settings
from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


def set_app_defaults(**values: Any) -> None:
    app_settings = get_or_create_app_settings()
    for field, value in values.items():
        setattr(app_settings, f"default_{field}", value)
    app_settings.save()


@pytest.fixture
def owner() -> Api:
    return Api(make_user("owner"))


def create(api: Api) -> dict[str, Any]:
    res = api.post("/calendars", {"name": "Work"})
    assert res.status_code == 200, res.content
    calendar: dict[str, Any] = res.json()
    return calendar


def test_a_new_calendar_follows_app_defaults_changed_later(owner: Api) -> None:
    calendar = create(owner)
    assert calendar["first_weekday"] == 1  # Monday
    assert Calendar.objects.get(id=calendar["id"]).first_weekday is None

    set_app_defaults(first_weekday=0, weekend_days=[5, 6])

    shown = owner.get(f"/calendars/{calendar['id']}").json()
    assert (shown["first_weekday"], shown["weekend_days"]) == (0, [5, 6])
    listed = next(
        item["calendar"] for item in owner.get("/calendars").json() if item["calendar"]["id"] == calendar["id"]
    )
    assert listed["first_weekday"] == 0


def test_a_layout_value_set_for_the_calendar_stays(owner: Api) -> None:
    calendar = create(owner)
    assert owner.patch(f"/calendars/{calendar['id']}", {"first_weekday": 1}).status_code == 200

    set_app_defaults(first_weekday=0, show_week_numbers=True)

    shown = owner.get(f"/calendars/{calendar['id']}").json()
    assert shown["first_weekday"] == 1
    assert shown["show_week_numbers"] is True


def test_null_puts_a_layout_value_back_to_the_app_default(owner: Api) -> None:
    calendar = create(owner)
    owner.patch(f"/calendars/{calendar['id']}", {"first_weekday": 3})
    set_app_defaults(first_weekday=1)

    res = owner.patch(f"/calendars/{calendar['id']}", {"first_weekday": None})
    assert res.status_code == 200, res.content
    assert res.json()["first_weekday"] == 1
