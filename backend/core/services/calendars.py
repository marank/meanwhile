"""
Creating calendars.
"""

from core.models import Calendar, CalendarMember, User
from core.models.base import Role
from core.models.calendar_colors import COLOR_FIELDS, DEFAULT_COLORS


def create_calendar(
    owner: User,
    name: str,
    description: str = "",
    force_all_day: bool = False,
    first_weekday: int | None = None,
    show_weekends: bool | None = None,
    weekend_days: list[int] | None = None,
    show_week_numbers: bool | None = None,
    colors: dict[str, str | None] | None = None,
    dav_name: str | None = None,
) -> Calendar:
    """A new calendar of `owner`; unset colors come from the defaults, an unset week layout follows the
    app's defaults (also when they change later)."""
    colors = colors or {}
    calendar = Calendar.objects.create(
        name=name,
        description=description,
        force_all_day=force_all_day,
        first_weekday=first_weekday,
        show_weekends=show_weekends,
        weekend_days=sorted(set(weekend_days)) if weekend_days is not None else None,
        show_week_numbers=show_week_numbers,
        **{field: colors.get(field) or DEFAULT_COLORS[field] for field in COLOR_FIELDS},
        owner=owner,
        dav_name=dav_name,
    )
    CalendarMember.objects.create(calendar=calendar, user=owner, role=Role.OWNER, folder_id=None, position=0)
    return calendar
