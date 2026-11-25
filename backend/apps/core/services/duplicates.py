"""
Copying an event to another date or calendar: a new event made with the checks of any new one
(bookings, approvals, conflicts, invitations).
"""

from datetime import datetime

from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import Calendar, Category, Event, Resource, ShowAs, User
from apps.core.schemas import EventCreate, EventParticipantCreate
from apps.core.services.attachments import copy_attachments
from apps.core.services.events import create_event
from apps.core.services.recurrence import as_utc, moved_rrule
from apps.core.services.reminders import reminder_minutes, set_reminders


def duplicate_event(user: User, source: Event, calendar: Calendar, start: datetime, *, invite: bool) -> Event:
    """A copy of `source` in `calendar` starting at `start`, as long as the original.

    A series is copied as a series (its changed and removed occurrences aside), a changed occurrence of
    one as a single event. Category, resource and booked location come along within the same calendar;
    into another one only a category of the same name. With `invite`, the participants are invited
    to the copy. The user's own reminders come along, and so do the attachments.
    """
    if calendar.force_all_day and not source.all_day:
        raise HttpError(422, gettext("This calendar only allows all-day events"))
    start = as_utc(start)
    if source.all_day:
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    by = start - as_utc(source.start)
    same_calendar = calendar.id == source.calendar_id
    rrule = moved_rrule(source, by) if source.parent_id is None else None
    location_resource = _still_bookable(source.location_resource) if same_calendar else None

    payload = EventCreate(
        title=source.title,
        description=source.description,
        location=source.location or None,
        location_resource_id=str(location_resource.id) if location_resource else None,
        start=start,
        end=as_utc(source.end) + by,
        all_day=source.all_day,
        timezone=source.timezone,
        show_recurrence_count=source.show_recurrence_count and rrule is not None,
        rrule=rrule,
        category_id=_category_id(source.category, calendar, same_calendar=same_calendar),
        resource_id=_resource_id(source.resource, same_calendar=same_calendar),
        show_as=ShowAs(source.show_as),
        participants=_participants(source, user) if invite else None,
    )
    copy = create_event(user, calendar, payload)
    set_reminders(copy, user, reminder_minutes(source, user))
    copy_attachments(source, copy, user)
    return copy


def _still_bookable(resource: Resource | None) -> Resource | None:
    if resource is None or not resource.is_active or resource.archived_at is not None:
        return None
    return resource


def _resource_id(resource: Resource | None, *, same_calendar: bool) -> str | None:
    # Resources belong to their calendar; a copy into another one books none.
    bookable = _still_bookable(resource) if same_calendar else None
    return str(bookable.id) if bookable else None


def _category_id(category: Category | None, calendar: Calendar, *, same_calendar: bool) -> str | None:
    if category is None:
        return None
    if same_calendar:
        return str(category.id)
    # Another calendar has categories of its own; one of the same name stands in.
    match = calendar.categories.filter(name__iexact=category.name).first()
    return str(match.id) if match else None


def _participants(source: Event, user: User) -> list[EventParticipantCreate]:
    """The source's participants, asked anew; the one copying it organizes the copy."""
    return [
        EventParticipantCreate(user_id=str(p.user_id)) if p.user_id else EventParticipantCreate(email=p.email)
        for p in source.participants.order_by("created_at")
        if p.user_id != user.id and p.email.lower() != user.email.lower()
    ]
