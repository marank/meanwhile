"""
Event and participant endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from ninja import Query, Router
from ninja.errors import HttpError

from core.models import Calendar, Category, Event, EventParticipant, Resource, User
from core.models.base import EventStatus, ParticipantStatus, Role
from core.schemas import (
    EventCreate,
    EventOut,
    EventParticipantCreate,
    EventParticipantInvite,
    EventParticipantOut,
    EventParticipantUpdate,
    EventRemindersIn,
    EventRemindersOut,
    EventUpdate,
    OccurrenceOut,
    OccurrenceScope,
    OkOut,
)
from core.services.activity import record_activity
from core.services.bookings import (
    approvers_of,
    awaiting_resources,
    booked_resources,
    decidable_resources,
    find_booking_conflicts,
    is_in_approver_pool,
    update_booking_status,
)
from core.services.itip import record_answer, send_cancel, send_request
from core.services.notifications import notify
from core.services.permissions import (
    MembershipInfo,
    can_modify_event,
    get_member_calendar,
    get_membership,
    get_visible_event,
    memberships_of,
    participant_event_ids,
)
from core.services.recurrence import (
    as_utc,
    expand_events,
    format_exdate,
    is_series,
    occurrence_index,
    parse_exdates,
    recurrence_count,
)
from core.services.reminders import reminder_minutes, set_reminders
from core.services.series import (
    end_before,
    is_occurrence,
    override_for,
    remap_exceptions,
    remove_occurrence,
    snapshot,
    split,
)
from core.views.common import AuthedRequest, serialize_event

# Called off: participants were told already.
_GONE = {EventStatus.REJECTED, EventStatus.CANCELLED}

router = Router()


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


def _tracked_values(event: Event) -> dict[str, Any]:
    return {field: getattr(event, attr) for field, attr in _TRACKED_FIELDS.items()}


def _occurrences(
    user: User, memberships: dict[UUID, MembershipInfo], range_start: datetime, range_end: datetime
) -> list[OccurrenceOut]:
    """Occurrences in the range of the calendars of `memberships` (the user's, by calendar id), by start,
    as visible to the user."""
    events = Event.objects.filter(
        Q(calendar_id__in=memberships),
        Q(start__lt=range_end),
        Q(rrule__isnull=False) | ~Q(rdates=[]) | Q(all_day=True) | Q(end__gt=range_start),
    ).select_related("calendar", "category", "resource", "location_resource")

    hidden = {EventStatus.REJECTED, EventStatus.CANCELLED}
    user_id = str(user.id)
    invited_to = participant_event_ids(user)
    can_decide: dict[tuple[object, ...], bool] = {}
    out: list[OccurrenceOut] = []
    for event, occ_start, occ_end in expand_events(events, range_start, range_end):
        if event.status in hidden and str(event.creator_id) != str(user_id):
            continue
        if event.status == EventStatus.PENDING and str(event.creator_id) != str(user_id) and event.id not in invited_to:
            # Pending bookings are only shown to the requester, participants and approvers.
            # The pool is the same for the same bookings of a calendar (its owner always decides).
            key = (event.calendar_id, *sorted(str(i) for i in event.awaiting_approval or []))
            if key not in can_decide:
                can_decide[key] = is_in_approver_pool(event, user_id)
            if not can_decide[key]:
                continue
        out.append(
            OccurrenceOut(
                event_id=str(event.id),
                calendar_id=str(event.calendar_id),
                title=event.title,
                description=event.description,
                start=occ_start,
                end=occ_end,
                all_day=event.all_day,
                recurrence_count=(
                    recurrence_count(event, occ_start) if event.show_recurrence_count and is_series(event) else None
                ),
                status=EventStatus(event.status),
                category_id=str(event.category_id) if event.category_id else None,
                category_name=event.category.name if event.category else None,
                category_color=event.category.color if event.category else None,
                resource_id=str(event.resource_id) if event.resource_id else None,
                resource_name=event.resource.name if event.resource else None,
                resource_icon=event.resource.icon if event.resource else "",
                location=event.location,
                location_resource_id=str(event.location_resource_id) if event.location_resource_id else None,
                location_resource_icon=event.location_resource.icon if event.location_resource else "",
                creator_id=str(event.creator_id),
                can_edit=can_modify_event(event, user_id, memberships[event.calendar_id].role),
                is_recurring=is_series(event) or bool(event.parent_id),
                series_id=str(event.parent_id or event.id) if is_series(event) or event.parent_id else None,
                recurrence_id=(
                    as_utc(event.recurrence_id)
                    if event.parent_id and event.recurrence_id
                    else occ_start
                    if is_series(event)
                    else None
                ),
            )
        )
    out.sort(key=lambda o: o.start)
    return out


def _parse_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    range_start = as_utc(start)
    range_end = as_utc(end)
    if range_start >= range_end:
        raise HttpError(422, "end must be after start")
    return range_start, range_end


@router.get("/events", response=list[OccurrenceOut])
def list_events_of_calendars(
    request: AuthedRequest,
    start: datetime,
    end: datetime,
    calendar_ids: Query[list[str]],
) -> list[OccurrenceOut]:
    """Occurrences of several calendars at once; calendars the user can't read are skipped."""
    range_start, range_end = _parse_range(start, end)
    memberships = memberships_of(request.user, Calendar.objects.filter(id__in=calendar_ids))
    return _occurrences(request.user, memberships, range_start, range_end)


@router.get("/calendars/{calendar_id}/events", response=list[OccurrenceOut])
def list_events(request: AuthedRequest, calendar_id: str, start: datetime, end: datetime) -> list[OccurrenceOut]:
    calendar, membership = get_member_calendar(calendar_id, request.user)
    range_start, range_end = _parse_range(start, end)
    return _occurrences(request.user, {calendar.id: membership}, range_start, range_end)


@router.post("/calendars/{calendar_id}/events", response=EventOut)
def create_event(request: AuthedRequest, calendar_id: str, payload: EventCreate) -> EventOut:
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.OWN, "You do not have permission to create events"
    )
    if calendar.force_all_day and not payload.all_day:
        raise HttpError(422, "This calendar only allows all-day events")

    start = as_utc(payload.start)
    end = as_utc(payload.end)
    if end < start or (end == start and not payload.all_day):
        raise HttpError(
            422,
            "end must not precede start for all-day events and must be after start otherwise",
        )

    category = None
    if payload.category_id:
        category = Category.objects.filter(id=payload.category_id, calendar=calendar).first()
        if category is None:
            raise HttpError(404, "Category not found")

    resource = _bookable(calendar, payload.resource_id, location=False)
    location_resource = _bookable(calendar, payload.location_resource_id, location=True)

    with transaction.atomic():
        event = Event(
            calendar=calendar,
            creator=request.user,
            title=payload.title if payload.title is not None else "",
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
        update_booking_status(event, request.user, booked_resources(event))
        event.save()
        _check_booking_conflicts(event)

        record_activity(event, str(request.user.id), "created")
        if payload.participants:
            for invite in payload.participants:
                _create_participant(event, request.user, invite)
            send_request(event)
        if event.status == EventStatus.PENDING:
            notify(
                [str(a.id) for a in approvers_of(awaiting_resources(event))] + [str(calendar.owner_id)],
                "approval_requested",
                str(request.user.id),
                event.title,
                calendar_id=str(calendar.id),
                event_id=str(event.id),
            )

    return EventOut.model_validate(serialize_event(event))


@router.get("/events/{event_id}", response=EventOut)
def get_event(request: AuthedRequest, event_id: str) -> EventOut:
    event, _ = get_visible_event(event_id, request.user)
    data = serialize_event(event)
    data["can_decide"] = event.status == EventStatus.PENDING and bool(decidable_resources(event, str(request.user.id)))
    return EventOut.model_validate(data)


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
            # Structured, which core.api.http_error passes through; Ninja types the message as a str.
            {  # type: ignore[arg-type]
                "message": "This booking conflicts with an approved booking",
                "conflicts": [str(c.id) for c in conflicts],
            },
        )


def _modifiable_event(event_id: str, user: User) -> tuple[Event, MembershipInfo]:
    event = Event.objects.select_related("calendar").get(id=event_id)
    membership = get_membership(event.calendar, user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not can_modify_event(event, str(user.id), membership.role):
        raise HttpError(403, "You do not have permission to edit this event")
    return event, membership


@router.patch("/events/{event_id}", response=EventOut)
def update_event(request: AuthedRequest, event_id: str, payload: EventUpdate) -> EventOut:
    event, _ = _modifiable_event(event_id, request.user)
    data = payload.dict(exclude_unset=True)
    if event.parent_id and data.get("rrule"):
        raise HttpError(422, "A changed occurrence of a series can't repeat itself")
    with transaction.atomic():
        _apply_update(request.user, event, data)
    return EventOut.model_validate(serialize_event(event))


def _apply_update(user: User, event: Event, data: dict[str, Any]) -> None:
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
    all_day = data["all_day"] if "all_day" in data else event.all_day
    if "start" in data or "end" in data or "all_day" in data:
        if end < start or (end == start and not all_day):
            raise HttpError(
                422,
                "end must not precede start for all-day events and must be after start otherwise",
            )

    category = event.category
    if "category_id" in data:
        if data["category_id"] is None:
            category = None
        else:
            category = Category.objects.filter(id=data["category_id"], calendar=calendar).first()
            if category is None:
                raise HttpError(404, "Category not found")

    resource = event.resource
    if "resource_id" in data:
        resource = _bookable(calendar, data["resource_id"], location=False)
    location_resource = event.location_resource
    if "location_resource_id" in data:
        location_resource = _bookable(calendar, data["location_resource_id"], location=True)
    elif location_resource and data.get("location") not in (None, location_resource.name):
        # Another location typed in place of the booked one gives that booking up.
        location_resource = None

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
    if "all_day" in data:
        event.all_day = data["all_day"]
    if "show_recurrence_count" in data:
        event.show_recurrence_count = data["show_recurrence_count"]
    if "rrule" in data:
        event.rrule = data["rrule"]
    if "category_id" in data:
        event.category_id = category.id if category else None

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
    if rescheduled and not event.parent_id:
        remap_exceptions(event, before)
        event.save()
    if rescheduled:
        # Answers were for the old time: participants are asked again (as Outlook and Google do),
        # except the one who moved it.
        EventParticipant.objects.filter(Q(event=event) | Q(event__parent=event)).exclude(user=user).exclude(
            status=ParticipantStatus.NEEDS_ACTION
        ).update(status=ParticipantStatus.NEEDS_ACTION)
    status_reset = event.status == EventStatus.PENDING and old_status != EventStatus.PENDING
    if changed:
        details: dict[str, list[str] | str] = {"fields": changed}
        if status_reset:
            details["status"] = "pending"
        record_activity(event, str(user.id), "updated", details)
    if status_reset:
        notify(
            [str(a.id) for a in approvers_of(awaiting_resources(event))] + [str(calendar.owner_id)],
            "approval_requested",
            str(user.id),
            event.title,
            calendar_id=str(calendar.id),
            event_id=str(event.id),
        )
    if status_reset or _SCHEDULED_FIELDS.intersection(changed):
        send_request(event, update=True)


@router.delete("/events/{event_id}", response=OkOut)
def delete_event(request: AuthedRequest, event_id: str) -> dict[str, bool]:
    event, _ = _modifiable_event(event_id, request.user)
    with transaction.atomic():
        if event.parent_id:
            series, rid = event.parent, event.recurrence_id
            # A changed occurrence belongs to a series and keeps the start it replaces.
            assert series is not None and rid is not None
            # Deleting a changed occurrence removes it from the series instead of restoring it.
            remove_occurrence(series, rid)
            details = _occurrence_details(rid)
            record_activity(series, str(request.user.id), "occurrence_deleted", details)
            send_request(series, update=True)
        else:
            # A cancelled or rejected event was called off already; participants don't hear it twice.
            if event.status not in _GONE:
                send_cancel(event)
            event.delete()
    return {"ok": True}


def _occurrence_details(start: datetime) -> dict[str, str]:
    return {"occurrence": as_utc(start).isoformat()}


def _series_occurrence(event_id: str, user: User, recurrence_id: datetime) -> Event:
    series, _ = _modifiable_event(event_id, user)
    if not is_series(series) or series.parent_id:
        raise HttpError(422, "This event is not a series")
    if not is_occurrence(series, recurrence_id):
        raise HttpError(404, "The series has no occurrence at that time")
    return series


@router.patch("/events/{event_id}/occurrences/{recurrence_id}", response=EventOut)
def update_occurrence(
    request: AuthedRequest,
    event_id: str,
    recurrence_id: datetime,
    payload: EventUpdate,
    scope: OccurrenceScope = "this",
) -> EventOut:
    """Changes one occurrence of a series ("this"), it and the later ones ("following"), or all.

    `recurrence_id` is the original start of the occurrence; start and end in the payload are
    the occurrence's new times. Returns the event that was changed.
    """
    rid = as_utc(recurrence_id)
    series = _series_occurrence(event_id, request.user, rid)
    data = payload.dict(exclude_unset=True)
    with transaction.atomic():
        if scope == "this":
            override = override_for(series, rid)
            _apply_update(request.user, override, data)
            record_activity(series, str(request.user.id), "occurrence_changed", _occurrence_details(rid))
            return EventOut.model_validate(serialize_event(override))
        index = occurrence_index(series, rid) if scope == "following" else 0
        if index is None:
            # A changed occurrence at a time the rule doesn't produce (a CalDAV client may store
            # one): there is no "following" to split off from it.
            raise HttpError(
                422, "This occurrence is no longer part of the series' rule; change it alone or the whole series"
            )
        if scope == "following" and index > 0:
            following = split(series, rid)
            record_activity(following, str(request.user.id), "created")
            record_activity(series, str(request.user.id), "series_ended", _occurrence_details(rid))
            send_request(series, update=True)
            _apply_update(request.user, following, data)
            return EventOut.model_validate(serialize_event(following))
        # The whole series: the occurrence's new times move the series by as much.
        occurrence_end = rid + (series.end - series.start)
        if "start" in data:
            data["start"] = series.start + (as_utc(data["start"]) - rid)
        if "end" in data:
            data["end"] = series.end + (as_utc(data["end"]) - occurrence_end)
        _apply_update(request.user, series, data)
        return EventOut.model_validate(serialize_event(series))


@router.delete("/events/{event_id}/occurrences/{recurrence_id}", response=OkOut)
def delete_occurrence(
    request: AuthedRequest, event_id: str, recurrence_id: datetime, scope: OccurrenceScope = "this"
) -> dict[str, bool]:
    """Removes one occurrence of a series ("this"), it and the later ones ("following"), or all."""
    rid = as_utc(recurrence_id)
    series = _series_occurrence(event_id, request.user, rid)
    with transaction.atomic():
        if scope == "all" or (scope == "following" and occurrence_index(series, rid) == 0):
            if series.status not in _GONE:
                send_cancel(series)
            series.delete()
            return {"ok": True}
        if scope == "following":
            end_before(series, rid)
            record_activity(series, str(request.user.id), "series_ended", _occurrence_details(rid))
        else:
            remove_occurrence(series, rid)
            record_activity(series, str(request.user.id), "occurrence_deleted", _occurrence_details(rid))
        send_request(series, update=True)
    return {"ok": True}


@router.get("/events/{event_id}/reminders", response=EventRemindersOut)
def get_reminders(request: AuthedRequest, event_id: str) -> dict[str, list[int]]:
    """The current user's own reminders for the event (of a series: for all its occurrences)."""
    event, _ = get_visible_event(event_id, request.user)
    return {"minutes": reminder_minutes(event, request.user)}


@router.put("/events/{event_id}/reminders", response=EventRemindersOut)
def put_reminders(request: AuthedRequest, event_id: str, payload: EventRemindersIn) -> dict[str, list[int]]:
    # Everyone who sees an event may be reminded of it, read-only members included; it concerns only them.
    event, _ = get_visible_event(event_id, request.user)
    return {"minutes": set_reminders(event, request.user, payload.minutes)}


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


def _serialize_participant(participant: EventParticipant) -> dict[str, Any]:
    return {
        "id": participant.id,
        "event_id": str(participant.event_id),
        "user_id": str(participant.user_id) if participant.user_id else None,
        "email": participant.email,
        "display_name": participant.user.display_name if participant.user else None,
        "status": participant.status,
        "created_at": participant.created_at,
        "updated_at": participant.updated_at,
    }


def _participant_event(event_id: str, user: User) -> tuple[Event, MembershipInfo]:
    # Like the event itself: a booking the user may not see (e.g. pending) doesn't show its participants.
    return get_visible_event(event_id, user)


# Invitations go out by email to any address, from the app's mail server: no user sends more than this
# many an hour, so the app isn't a way to spam people.
MAX_INVITATIONS_PER_HOUR = 100


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


def _create_participant(
    event: Event, current_user: User, data: EventParticipantCreate | EventParticipantInvite
) -> EventParticipant:
    participant_status = data.status or ParticipantStatus.NEEDS_ACTION
    if data.user_id is not None:
        user = User.objects.filter(id=data.user_id).first()
        if user is None:
            raise HttpError(404, "User not found")
        email = user.email.lower()
    else:
        email = str(data.email).lower()
        user = User.objects.filter(email=email).first()

    q = Q(event=event, email=email)
    if user:
        q |= Q(event=event, user=user)
    if EventParticipant.objects.filter(q).exists():
        raise HttpError(400, "Participant already exists")
    _count_invitation(current_user)

    participant = EventParticipant.objects.create(
        event=event,
        user=user,
        email=email,
        status=participant_status,
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


@router.get("/events/{event_id}/participants", response=list[EventParticipantOut])
def list_event_participants(request: AuthedRequest, event_id: str) -> list[dict[str, Any]]:
    event, _ = _participant_event(event_id, request.user)
    participants = EventParticipant.objects.filter(event=event).select_related("user").order_by("created_at")
    return [_serialize_participant(p) for p in participants]


@router.post("/events/{event_id}/participants", response=EventParticipantOut)
def add_event_participant(request: AuthedRequest, event_id: str, payload: EventParticipantCreate) -> dict[str, Any]:
    event, membership = _participant_event(event_id, request.user)
    if not can_modify_event(event, str(request.user.id), membership.role):
        raise HttpError(403, "You cannot modify this event")
    with transaction.atomic():
        participant = _create_participant(event, request.user, payload)
        send_request(event, [participant])
    return _serialize_participant(participant)


@router.patch("/events/{event_id}/participants/me", response=EventParticipantOut)
def update_my_participation(request: AuthedRequest, event_id: str, payload: EventParticipantUpdate) -> dict[str, Any]:
    """Answers an invitation: sets the status of the current user's own participation."""
    try:
        participant = EventParticipant.objects.select_related("user").get(event_id=event_id, user=request.user)
    except EventParticipant.DoesNotExist:
        raise HttpError(404, "You are not a participant of this event") from None
    with transaction.atomic():
        record_answer(participant, payload.status)
    return _serialize_participant(participant)


@router.patch("/events/{event_id}/participants/{participant_id}", response=EventParticipantOut)
def update_event_participant(
    request: AuthedRequest, event_id: str, participant_id: str, payload: EventParticipantUpdate
) -> dict[str, Any]:
    event = Event.objects.get(id=event_id)
    participant = EventParticipant.objects.get(id=participant_id, event=event)
    membership = get_membership(event.calendar, request.user)
    can_modify = membership is not None and can_modify_event(event, str(request.user.id), membership.role)
    if not (can_modify or participant.user_id == request.user.id):
        raise HttpError(403, "You cannot update this participant")
    with transaction.atomic():
        if participant.user_id == request.user.id:
            record_answer(participant, payload.status)
        else:
            participant.status = payload.status
            participant.save()
    return _serialize_participant(participant)


@router.delete("/events/{event_id}/participants/{participant_id}", response=OkOut)
def delete_event_participant(request: AuthedRequest, event_id: str, participant_id: str) -> dict[str, bool]:
    event = Event.objects.get(id=event_id)
    participant = EventParticipant.objects.get(id=participant_id, event=event)
    membership = get_membership(event.calendar, request.user)
    can_modify = membership is not None and can_modify_event(event, str(request.user.id), membership.role)
    if not (can_modify or participant.user_id == request.user.id):
        raise HttpError(403, "You cannot remove this participant")
    with transaction.atomic():
        # Taken off by someone else: told so, for the event or (a changed occurrence) that occurrence only.
        if participant.user_id != request.user.id:
            send_cancel(event, [participant])
        participant.delete()
    return {"ok": True}
