"""
Creating calendars and changing their details.
"""

from typing import Any

from django.db import IntegrityError, transaction
from ninja.errors import HttpError

from apps.core.models import Calendar, CalendarMember, User, as_uuid
from apps.core.models.base import Role
from apps.core.models.calendar_colors import COLOR_FIELDS, DEFAULT_COLORS


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


def _require_free_url_path(calendar: Calendar, url_path: str) -> None:
    # Taken by the app's own URLs: /calendar/folder/<id> and /calendar/all.
    if url_path in {"folder", "all"}:
        raise HttpError(422, "This calendar URL is reserved")
    others = Calendar.objects.exclude(id=calendar.id)
    if others.filter(url_path=url_path).exists():
        raise HttpError(409, "This calendar URL is already in use")
    if (path_id := as_uuid(url_path)) and others.filter(id=path_id).exists():
        raise HttpError(409, "This calendar URL is already in use")


def update_calendar(calendar: Calendar, data: dict[str, Any]) -> Calendar:
    """Changes what `data` names (the PATCH's set fields)."""
    if data.get("weekend_days") is not None:
        data["weekend_days"] = sorted(set(data["weekend_days"]))
    if data.get("url_path") is not None:
        _require_free_url_path(calendar, data["url_path"])
    for attr, value in data.items():
        setattr(calendar, attr, value)
    try:
        with transaction.atomic():
            calendar.save()
    except IntegrityError as error:
        if "url_path" in data:
            raise HttpError(409, "This calendar URL is already in use") from error
        raise
    return calendar
