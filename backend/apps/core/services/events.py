"""
Creating and changing events and inviting participants: the checks and side effects of each write.
"""

from datetime import datetime
from typing import Any

from django.core.cache import cache
from django.db.models import Q
from ninja.errors import HttpError

from apps.core.models import Calendar, Category, Event, EventParticipant, Resource, User
from apps.core.models.base import EventStatus, ParticipantStatus
from apps.core.schemas import EventCreate, EventParticipantCreate
from apps.core.services.activity import record_activity
from apps.core.services.bookings import (
    approvers_of,
    awaiting_resources,
    booked_resources,
    find_booking_conflicts,
    update_booking_status,
)
from apps.core.services.itip import send_request
from apps.core.services.notifications import notify
from apps.core.services.recurrence import as_utc, format_exdate, parse_exdates
from apps.core.services.series import remap_exceptions, snapshot

# Changes that participants are sent (the rest, e.g. the category, concern the calendar only).
_SCHEDULED_FIELDS = {"title", "description", "location", "start", "end", "all_day", "rrule"}

# What the activity log records as changed by an edit, by name: the attribute that holds it.
_TRACKED_FIELDS = {
    "title": "title",
    "description": "description",
    "location": "location",
    "start": "start",
    "end": "end",
    "all_day": "all_day",
    "rrule": "rrule",
    "category": "category_id",
    "resource": "resource_id",
    "location_resource": "location_resource_id",
    "show_recurrence_count": "show_recurrence_count",
}

# Invitations go out by email to any address, from the app's mail server: no user sends more than this
# many an hour, so the app isn't a way to spam people.
MAX_INVITATIONS_PER_HOUR = 100


def create_event(user: User, calendar: Calendar, payload: EventCreate) -> Event:
    if calendar.force_all_day and not payload.all_day:
        raise HttpError(422, "This calendar only allows all-day events")
    start = as_utc(payload.start)
    end = as_utc(payload.end)
    _check_times(start, end, payload.all_day)
    category = _category(calendar, payload.category_id) if payload.category_id else None
    resource = _bookable(calendar, payload.resource_id, location=False)
    location_resource = _bookable(calendar, payload.location_resource_id, location=True)

    event = Event(
        calendar=calendar,
        creator=user,
        title=payload.title or "",
        description=payload.description,
        location=location_resource.name if location_resource else (payload.location or ""),
        start=start,
        end=end,
        all_day=payload.all_day,
        timezone=payload.timezone or "UTC",
        show_recurrence_count=payload.show_recurrence_count,
        rrule=payload.rrule,
        category=category,
        resource=resource,
        location_resource=location_resource,
    )
    event.uid = str(event.id)
    update_booking_status(event, user, booked_resources(event))
    event.save()
    _check_booking_conflicts(event)

    record_activity(event, str(user.id), "created")
    if payload.participants:
        for invite in payload.participants:
            add_participant(event, user, invite)
        send_request(event)
    if event.status == EventStatus.PENDING:
        _notify_approval_requested(event, user)
    return event


def update_event(user: User, event: Event, data: dict[str, Any]) -> None:
    """Applies the fields in `data` to the event, with the checks and side effects of an edit."""
    calendar = event.calendar
    if calendar.force_all_day and data.get("all_day") is False:
        raise HttpError(422, "This calendar only allows all-day events")
    if event.parent_id:
        # A changed occurrence takes its recurrence from the series.
        data.pop("rrule", None)
        data.pop("show_recurrence_count", None)

    before = snapshot(event)
    old_status = event.status
    old_values = _tracked_values(event)

    start = as_utc(data["start"]) if "start" in data else event.start
    end = as_utc(data["end"]) if "end" in data else event.end
    if "start" in data or "end" in data or "all_day" in data:
        _check_times(start, end, data.get("all_day", event.all_day))

    resource, location_resource = _new_bookings(event, data)
    _apply_fields(event, data, start, end, location_resource)

    # Compare values rather than the presence of keys: the event dialog resends every field.
    rescheduled = (
        event.start != old_values["start"]
        or event.end != old_values["end"]
        or event.all_day != old_values["all_day"]
        or event.rrule != old_values["rrule"]
    )
    # Clients send their zone with every save; it only replaces the event's zone along with a new
    # schedule, so editing e.g. the title from another zone leaves the series where it is.
    if rescheduled and data.get("timezone"):
        event.timezone = data["timezone"]
    resource_changed = (resource.id if resource else None) != old_values["resource"]
    location_changed = (location_resource.id if location_resource else None) != old_values["location_resource"]
    event.resource = resource
    event.location_resource = location_resource

    # New bookings, and all bookings at a new time, need approval again unless the user may
    # approve them; the others keep their state.
    candidates = ((resource, resource_changed), (location_resource, location_changed))
    recheck = [r for r, changed in candidates if r and changed]
    active = event.status in {EventStatus.APPROVED, EventStatus.CONFIRMED, EventStatus.PENDING}
    if rescheduled and active:
        recheck = booked_resources(event)
    if resource_changed or location_changed or (rescheduled and active):
        update_booking_status(event, user, recheck)
    _check_booking_conflicts(event)

    changed = [field for field, value in _tracked_values(event).items() if value != old_values[field]]

    event.save()
    if rescheduled:
        _reschedule(event, user, before)
    status_reset = event.status == EventStatus.PENDING and old_status != EventStatus.PENDING
    if changed:
        details: dict[str, list[str] | str] = {"fields": changed}
        if status_reset:
            details["status"] = "pending"
        record_activity(event, str(user.id), "updated", details)
    if status_reset:
        _notify_approval_requested(event, user)
    if status_reset or _SCHEDULED_FIELDS.intersection(changed):
        send_request(event, update=True, before={"id": event.id, **old_values})


def _new_bookings(event: Event, data: dict[str, Any]) -> tuple[Resource | None, Resource | None]:
    """The resource and the location (a resource too) the event books after the edit."""
    resource = event.resource
    if "resource_id" in data:
        resource = _bookable(event.calendar, data["resource_id"], location=False)
    location_resource = event.location_resource
    if "location_resource_id" in data:
        location_resource = _bookable(event.calendar, data["location_resource_id"], location=True)
    elif location_resource and data.get("location") not in (None, location_resource.name):
        # Another location typed in place of the booked one gives that booking up.
        location_resource = None
    return resource, location_resource


def _apply_fields(
    event: Event, data: dict[str, Any], start: datetime, end: datetime, location_resource: Resource | None
) -> None:
    """Sets the event's own fields from `data`; bookings and their state are the caller's."""
    if "category_id" in data:
        event.category = _category(event.calendar, data["category_id"]) if data["category_id"] else None
    if "title" in data:
        event.title = data["title"] or ""
    if "description" in data:
        event.description = data["description"]
    if location_resource is not None:
        event.location = location_resource.name
    elif "location" in data:
        event.location = data["location"] or ""
    if "start" in data:
        if event.rdates and not event.parent_id:
            # Moving the series moves its extra dates along.
            delta = start - event.start
            event.rdates = sorted(format_exdate(d + delta) for d in parse_exdates(event.rdates))
        event.start = start
    if "end" in data:
        event.end = end
    for field in ("all_day", "show_recurrence_count", "rrule"):
        if field in data:
            setattr(event, field, data[field])


def _reschedule(event: Event, user: User, before: Any) -> None:
    """After a saved change of time: the series' exceptions follow, and answers are asked again."""
    if not event.parent_id:
        remap_exceptions(event, before)
        event.save()
    # Answers were for the old time: participants are asked again (as Outlook and Google do),
    # except the one who moved it.
    EventParticipant.objects.filter(Q(event=event) | Q(event__parent=event)).exclude(user=user).exclude(
        status=ParticipantStatus.NEEDS_ACTION
    ).update(status=ParticipantStatus.NEEDS_ACTION)


def add_participant(event: Event, current_user: User, data: EventParticipantCreate) -> EventParticipant:
    if data.user_id is not None:
        user = User.objects.filter(id=data.user_id).first()
        if user is None:
            raise HttpError(404, "User not found")
        email = user.email.lower()
    else:
        email = str(data.email).lower()
        user = User.objects.filter(email__iexact=email).first()

    q = Q(event=event, email=email)
    if user:
        q |= Q(event=event, user=user)
    if EventParticipant.objects.filter(q).exists():
        raise HttpError(400, "Participant already exists")
    _count_invitation(current_user)

    participant = EventParticipant.objects.create(
        event=event, user=user, email=email, status=data.status or ParticipantStatus.NEEDS_ACTION
    )
    if user:
        notify(
            [str(user.id)],
            "participant_added",
            str(current_user.id),
            event.title or "Untitled event",
            calendar_id=str(event.calendar_id),
            event_id=str(event.id),
            data={"email": email},
        )
    return participant


def _tracked_values(event: Event) -> dict[str, Any]:
    return {field: getattr(event, attr) for field, attr in _TRACKED_FIELDS.items()}


def _check_times(start: datetime, end: datetime, all_day: bool) -> None:
    if end < start or (end == start and not all_day):
        raise HttpError(422, "end must not precede start for all-day events and must be after start otherwise")


def _category(calendar: Calendar, category_id: str) -> Category:
    category = Category.objects.filter(id=category_id, calendar=calendar).first()
    if category is None:
        raise HttpError(404, "Category not found")
    return category


def _bookable(calendar: Calendar, resource_id: str | None, location: bool) -> Resource | None:
    """A resource of the calendar that can be booked now, as location or as resource."""
    if not resource_id:
        return None
    resource = Resource.objects.filter(
        id=resource_id, calendar=calendar, is_active=True, archived_at__isnull=True, is_location=location
    ).first()
    if resource is None:
        raise HttpError(404, "Location not found" if location else "Resource not found")
    return resource


def _check_booking_conflicts(event: Event) -> None:
    conflicts = find_booking_conflicts(event)
    if conflicts:
        raise HttpError(
            409,
            # Structured, which apps.core.api.http_error passes through; Ninja types the message as a str.
            {  # type: ignore[arg-type]
                "message": "This booking conflicts with an approved booking",
                "conflicts": [str(c.id) for c in conflicts],
            },
        )


def _notify_approval_requested(event: Event, requester: User) -> None:
    notify(
        [str(a.id) for a in approvers_of(awaiting_resources(event))] + [str(event.calendar.owner_id)],
        "approval_requested",
        str(requester.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
    )


def _count_invitation(user: User) -> None:
    key = f"invitations:{user.id}"
    if cache.add(key, 1, timeout=3600):
        return
    try:
        count = cache.incr(key)
    except ValueError:  # expired in between
        cache.add(key, 1, timeout=3600)
        return
    if count > MAX_INVITATIONS_PER_HOUR:
        raise HttpError(429, "Too many invitations; try again in an hour")
