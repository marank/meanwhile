"""
Week layouts, which fall back to the app's defaults, and the overview's settings.
"""

from typing import Any, cast

from ninja import Field

from apps.core.models.users import get_or_create_app_settings
from apps.core.schemas.common import Color, Schema, Weekday


class WeekLayoutOut(Schema):
    """The week layout of a calendar or the overview; what isn't set there follows the app's defaults."""

    first_weekday: int
    show_weekends: bool
    weekend_days: list[Weekday]
    show_week_numbers: bool

    @staticmethod
    def resolve_first_weekday(obj: object, context: dict[str, Any] | None) -> int:
        return cast(int, _layout_value(obj, "first_weekday", context))

    @staticmethod
    def resolve_show_weekends(obj: object, context: dict[str, Any] | None) -> bool:
        return cast(bool, _layout_value(obj, "show_weekends", context))

    @staticmethod
    def resolve_weekend_days(obj: object, context: dict[str, Any] | None) -> list[int]:
        return cast(list[int], _layout_value(obj, "weekend_days", context))

    @staticmethod
    def resolve_show_week_numbers(obj: object, context: dict[str, Any] | None) -> bool:
        return cast(bool, _layout_value(obj, "show_week_numbers", context))


def _layout_value(obj: object, field: str, context: dict[str, Any] | None) -> Any:
    value = obj[field] if isinstance(obj, dict) else getattr(obj, field)
    if value is not None:
        return value
    # Loaded once per request, however many calendars are listed.
    request = (context or {}).get("request")
    app_settings = getattr(request, "_app_settings", None)
    if app_settings is None:
        app_settings = get_or_create_app_settings()
        if request is not None:
            request._app_settings = app_settings
    return getattr(app_settings, f"default_{field}")


class OverviewSettingsOut(WeekLayoutOut):
    use_calendar_colors: bool
    base_color: str
    weekend_color: str
    today_color: str
    event_color: str
    border_color: str
    outer_border_color: str
    dark_base_color: str
    dark_weekend_color: str
    dark_today_color: str
    dark_event_color: str
    dark_border_color: str
    dark_outer_border_color: str


class OverviewSettingsUpdate(Schema):
    first_weekday: int | None = Field(None, ge=0, le=6)
    show_weekends: bool | None = None
    weekend_days: list[Weekday] | None = None
    show_week_numbers: bool | None = None
    use_calendar_colors: bool | None = None
    base_color: Color | None = None
    weekend_color: Color | None = None
    today_color: Color | None = None
    event_color: Color | None = None
    border_color: Color | None = None
    outer_border_color: Color | None = None
    dark_base_color: Color | None = None
    dark_weekend_color: Color | None = None
    dark_today_color: Color | None = None
    dark_event_color: Color | None = None
    dark_border_color: Color | None = None
    dark_outer_border_color: Color | None = None
