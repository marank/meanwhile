"""
Creating calendars.
"""

import secrets

from core.models import Calendar, CalendarMember, User
from core.models.base import Role
from core.models.calendar_colors import COLOR_FIELDS, DEFAULT_COLORS
from core.models.users import get_or_create_app_settings


def create_calendar(
    owner: User,
    name: str,
    description: str | None = None,
    force_all_day: bool = False,
    first_weekday: int | None = None,
    show_weekends: bool | None = None,
    weekend_days: list[int] | None = None,
    show_week_numbers: bool | None = None,
    colors: dict[str, str | None] | None = None,
    dav_name: str | None = None,
) -> Calendar:
    """A new calendar of `owner`; unset layout settings and colors come from the app defaults."""
    app_settings = get_or_create_app_settings()
    colors = colors or {}
    calendar = Calendar.objects.create(
        name=name,
        description=description,
        force_all_day=force_all_day,
        first_weekday=first_weekday if first_weekday is not None else app_settings.default_first_weekday,
        show_weekends=show_weekends if show_weekends is not None else app_settings.default_show_weekends,
        weekend_days=sorted(set(weekend_days)) if weekend_days is not None else app_settings.default_weekend_days,
        show_week_numbers=(
            show_week_numbers if show_week_numbers is not None else app_settings.default_show_week_numbers
        ),
        **{field: colors.get(field) or DEFAULT_COLORS[field] for field in COLOR_FIELDS},
        owner=owner,
        feed_token=secrets.token_urlsafe(32),
        dav_name=dav_name,
    )
    CalendarMember.objects.create(calendar=calendar, user=owner, role=Role.OWNER, folder_id=None, position=0)
    return calendar
