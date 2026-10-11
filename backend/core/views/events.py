"""
Event and participant endpoints.
"""

from datetime import datetime

from django.db import transaction
from django.db.models import Q
from ninja import Query
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Calendar, Category, Event, EventParticipant, Resource, User
from core.models.base import EventStatus, Role
from core.schemas import (
    EventCreate,
    EventOut,
    EventParticipantCreate,
    EventParticipantOut,
    EventParticipantUpdate,
    EventRemindersIn,
    EventRemindersOut,
    EventUpdate,
    OccurrenceOut,
    OccurrenceScope,
)
from core.services.activity import record_activity
from core.services.bookings import (
    approvers_of,
    awaiting_resources,
    booked_resources,
    can_modify_event,
    decidable_resources,
    find_booking_conflicts,
    is_in_approver_pool,
    update_booking_status,
)
from core.services.notifications import notify
from core.services.permissions import (
    get_membership,
    get_visible_event,
    has_at_least_role,
    participant_event_ids,
)
from core.services.recurrence import (
    expand_events,
    format_exdate,
    is_series,
    make_aware,
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

router = CSRFRouter()


PARTICIPANT_STATUSES = {"needs_action", "accepted", "declined", "tentative"}


def _serialize_event(event: Event) -> dict:
    return {
        "id": event.id,
        "calendar_id": str(event.calendar_id),
        "creator_id": str(event.creator_id),
        "creator_name": event.creator_name,
        "creator_email": event.creator_email,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "location_resource_id": str(event.location_resource_id) if event.location_resource_id else None,
        "location_resource_name": event.location_resource.name if event.location_resource else None,
        "start": make_aware(event.start),
        "end": make_aware(event.end),
        "all_day": event.all_day,
        "timezone": event.timezone,
        "show_recurrence_count": event.show_recurrence_count,
        "rrule": event.rrule,
        "rdates": event.rdates or [],
        "uid": event.uid,
        "parent_id": str(event.parent_id) if event.parent_id else None,
        "recurrence_id": make_aware(event.recurrence_id) if event.recurrence_id else None,
        "category_id": str(event.category_id) if event.category_id else None,
        "category_name": event.category.name if event.category else None,
        "category_color": event.category.color if event.category else None,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "resource_name": event.resource.name if event.resource else None,
        "status": event.status,
        "awaiting_approval": [r.name for r in awaiting_resources(event)],
        "decided_by": str(event.decided_by_id) if event.decided_by_id else None,
        "decided_at": event.decided_at,
        "decision_note": event.decision_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def _calendar_occurrences(user, calendar: Calendar, membership, range_start: datetime, range_end: datetime) -> list[OccurrenceOut]:
    """Occurrences of one calendar in the range, as visible to `user`."""
    events = Event.objects.filter(
        Q(calendar=calendar),
        Q(start__lt=range_end),
        Q(rrule__isnull=False) | ~Q(rdates=[]) | Q(all_day=True) | Q(end__gt=range_start),
    ).select_related("calendar", "category", "resource", "location_resource")

    hidden = {EventStatus.REJECTED, EventStatus.CANCELLED}
    user_id = str(user.id)
    invited_to = participant_event_ids(user)
    can_decide: dict[tuple, bool] = {}
    out = []
    for event, occ_start, occ_end in expand_events(events, range_start, range_end):
        if event.status in hidden and str(event.creator_id) != user_id:
            continue
        if event.status == EventStatus.PENDING and str(event.creator_id) != user_id and event.id not in invited_to:
            # Pending bookings are only shown to the requester, participants and approvers.
            key = tuple(sorted(str(i) for i in event.awaiting_approval or []))
            if key not in can_decide:
                can_decide[key] = is_in_approver_pool(event, user_id=user_id)
            if not can_decide[key]:
                continue
        out.append(OccurrenceOut(
            event_id=str(event.id),
            calendar_id=str(event.calendar_id),
            title=event.title,
            description=event.description,
            start=occ_start,
            end=occ_end,
            all_day=event.all_day,
            recurrence_count=(
                recurrence_count(event, occ_start)
                if event.show_recurrence_count and is_series(event)
                else None
            ),
            status=event.status,
            category_id=str(event.category_id) if event.category_id else None,
            category_name=event.category.name if event.category else None,
            category_color=event.category.color if event.category else None,
            resource_id=str(event.resource_id) if event.resource_id else None,
            resource_name=event.resource.name if event.resource else None,
            location=event.location,
            location_resource_id=str(event.location_resource_id) if event.location_resource_id else None,
            creator_id=str(event.creator_id),
            can_edit=can_modify_event(event, user_id, membership.role),
            is_recurring=is_series(event) or bool(event.parent_id),
            series_id=str(event.parent_id or event.id) if is_series(event) or event.parent_id else None,
            recurrence_id=(
                make_aware(event.recurrence_id) if event.parent_id else occ_start if is_series(event) else None
            ),
        ))
    return out


def _parse_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    range_start = make_aware(start)
    range_end = make_aware(end)
    if range_start >= range_end:
        raise HttpError(422, "end must be after start")
    return range_start, range_end


@router.get("/events", response=list[OccurrenceOut], auth=django_auth)
def list_events_of_calendars(
    request,
    start: datetime,
    end: datetime,
    calendar_ids: list[str] = Query(...),
):
    """Occurrences of several calendars at once; calendars the user can't read are skipped."""
    range_start, range_end = _parse_range(start, end)
    out = []
    for calendar in Calendar.objects.filter(id__in=calendar_ids):
        membership = get_membership(calendar, request.user)
        if membership is not None:
            out.extend(_calendar_occurrences(request.user, calendar, membership, range_start, range_end))
    out.sort(key=lambda x: x.start)
    return out


@router.get("/calendars/{calendar_id}/events", response=list[OccurrenceOut], auth=django_auth)
def list_events(request, calendar_id: str, start: datetime, end: datetime):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    range_start, range_end = _parse_range(start, end)
    out = _calendar_occurrences(request.user, calendar, membership, range_start, range_end)
    out.sort(key=lambda x: x.start)
    return out


@router.post("/calendars/{calendar_id}/events", response=EventOut, auth=django_auth)
def create_event(request, calendar_id: str, payload: EventCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not has_at_least_role(membership, Role.CONTRIBUTOR):
        raise HttpError(403, "You do not have permission to create events")
    if calendar.force_all_day and not payload.all_day:
        raise HttpError(422, "This calendar only allows all-day events")

    start = make_aware(payload.start)
    end = make_aware(payload.end)
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
        if event.status == EventStatus.PENDING:
            notify(
                [str(a.id) for a in approvers_of(awaiting_resources(event))] + [str(calendar.owner_id)],
                "approval_requested",
                str(request.user.id),
                event.title,
                calendar_id=str(calendar.id),
                event_id=str(event.id),
            )

    return EventOut.model_validate(_serialize_event(event))


@router.get("/events/{event_id}", response=EventOut, auth=django_auth)
def get_event(request, event_id: str):
    event, _ = get_visible_event(event_id, request.user)
    data = _serialize_event(event)
    data["can_decide"] = event.status == EventStatus.PENDING and bool(
        decidable_resources(event, str(request.user.id))
    )
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
            {
                "message": "This booking conflicts with an approved booking",
                "conflicts": [str(c.id) for c in conflicts],
            },
        )


def _modifiable_event(event_id: str, user: User) -> tuple[Event, object]:
    try:
        event = Event.objects.select_related("calendar").get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    membership = get_membership(event.calendar, user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not can_modify_event(event, str(user.id), membership.role):
        raise HttpError(403, "You do not have permission to edit this event")
    return event, membership


@router.patch("/events/{event_id}", response=EventOut, auth=django_auth)
def update_event(request, event_id: str, payload: EventUpdate):
    event, _ = _modifiable_event(event_id, request.user)
    data = payload.dict(exclude_unset=True)
    if event.parent_id and data.get("rrule"):
        raise HttpError(422, "A changed occurrence of a series can't repeat itself")
    with transaction.atomic():
        _apply_update(request, event, data)
    return EventOut.model_validate(_serialize_event(event))


def _apply_update(request, event: Event, data: dict) -> None:
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
    old_values = {
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "start": make_aware(event.start),
        "end": make_aware(event.end),
        "all_day": event.all_day,
        "rrule": event.rrule,
        "category": event.category_id,
        "resource": event.resource_id,
        "location_resource": event.location_resource_id,
        "show_recurrence_count": event.show_recurrence_count,
    }

    start = make_aware(data["start"]) if "start" in data else make_aware(event.start)
    end = make_aware(data["end"]) if "end" in data else make_aware(event.end)
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
            category = Category.objects.filter(
                id=data["category_id"], calendar=calendar
            ).first()
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
            delta = start - make_aware(event.start)
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
        make_aware(event.start) != old_values["start"]
        or make_aware(event.end) != old_values["end"]
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
    recheck = [r for r, changed in ((resource, resource_changed), (location_resource, location_changed)) if r and changed]
    active = event.status in {EventStatus.APPROVED, EventStatus.CONFIRMED, EventStatus.PENDING}
    if rescheduled and active:
        recheck = booked_resources(event)
    if resource_changed or location_changed or (rescheduled and active):
        update_booking_status(event, request.user, recheck)
    _check_booking_conflicts(event)

    changed = []
    for field, attr in (
        ("title", "title"),
        ("description", "description"),
        ("location", "location"),
        ("start", "start"),
        ("end", "end"),
        ("all_day", "all_day"),
        ("rrule", "rrule"),
        ("category", "category_id"),
        ("resource", "resource_id"),
        ("location_resource", "location_resource_id"),
        ("show_recurrence_count", "show_recurrence_count"),
    ):
        value = getattr(event, attr)
        if attr in ("start", "end"):
            value = make_aware(value)
        if value != old_values[field]:
            changed.append(field)

    event.save()
    if rescheduled and not event.parent_id:
        remap_exceptions(event, before)
        event.save()
    status_reset = (
        event.status == EventStatus.PENDING and old_status != EventStatus.PENDING
    )
    if changed:
        details = {"fields": changed}
        if status_reset:
            details["status"] = "pending"
        record_activity(event, str(request.user.id), "updated", details)
    if status_reset:
        notify(
            [str(a.id) for a in approvers_of(awaiting_resources(event))] + [str(calendar.owner_id)],
            "approval_requested",
            str(request.user.id),
            event.title,
            calendar_id=str(calendar.id),
            event_id=str(event.id),
        )


@router.delete("/events/{event_id}", auth=django_auth)
def delete_event(request, event_id: str):
    event, _ = _modifiable_event(event_id, request.user)
    with transaction.atomic():
        if event.parent_id:
            # Deleting a changed occurrence removes it from the series instead of restoring it.
            remove_occurrence(event.parent, event.recurrence_id)
            record_activity(event.parent, str(request.user.id), "occurrence_deleted", _occurrence_details(event.recurrence_id))
        else:
            event.delete()
    return {"ok": True}


def _occurrence_details(start: datetime) -> dict:
    return {"occurrence": make_aware(start).isoformat()}


def _series_occurrence(event_id: str, user: User, recurrence_id: datetime) -> Event:
    series, _ = _modifiable_event(event_id, user)
    if not is_series(series) or series.parent_id:
        raise HttpError(422, "This event is not a series")
    if not is_occurrence(series, recurrence_id):
        raise HttpError(404, "The series has no occurrence at that time")
    return series


@router.patch("/events/{event_id}/occurrences/{recurrence_id}", response=EventOut, auth=django_auth)
def update_occurrence(
    request, event_id: str, recurrence_id: datetime, payload: EventUpdate, scope: OccurrenceScope = "this"
):
    """Changes one occurrence of a series ("this"), it and the later ones ("following"), or all.

    `recurrence_id` is the original start of the occurrence; start and end in the payload are
    the occurrence's new times. Returns the event that was changed.
    """
    rid = make_aware(recurrence_id)
    series = _series_occurrence(event_id, request.user, rid)
    data = payload.dict(exclude_unset=True)
    with transaction.atomic():
        if scope == "this":
            override = override_for(series, rid)
            _apply_update(request, override, data)
            record_activity(series, str(request.user.id), "occurrence_changed", _occurrence_details(rid))
            return EventOut.model_validate(_serialize_event(override))
        if scope == "following" and occurrence_index(series, rid) > 0:
            following = split(series, rid)
            record_activity(following, str(request.user.id), "created")
            record_activity(series, str(request.user.id), "series_ended", _occurrence_details(rid))
            _apply_update(request, following, data)
            return EventOut.model_validate(_serialize_event(following))
        # The whole series: the occurrence's new times move the series by as much.
        occurrence_end = rid + (make_aware(series.end) - make_aware(series.start))
        if "start" in data:
            data["start"] = make_aware(series.start) + (make_aware(data["start"]) - rid)
        if "end" in data:
            data["end"] = make_aware(series.end) + (make_aware(data["end"]) - occurrence_end)
        _apply_update(request, series, data)
        return EventOut.model_validate(_serialize_event(series))


@router.delete("/events/{event_id}/occurrences/{recurrence_id}", auth=django_auth)
def delete_occurrence(request, event_id: str, recurrence_id: datetime, scope: OccurrenceScope = "this"):
    """Removes one occurrence of a series ("this"), it and the later ones ("following"), or all."""
    rid = make_aware(recurrence_id)
    series = _series_occurrence(event_id, request.user, rid)
    with transaction.atomic():
        if scope == "all" or (scope == "following" and occurrence_index(series, rid) == 0):
            series.delete()
        elif scope == "following":
            end_before(series, rid)
            record_activity(series, str(request.user.id), "series_ended", _occurrence_details(rid))
        else:
            remove_occurrence(series, rid)
            record_activity(series, str(request.user.id), "occurrence_deleted", _occurrence_details(rid))
    return {"ok": True}


@router.get("/events/{event_id}/reminders", response=EventRemindersOut, auth=django_auth)
def get_reminders(request, event_id: str):
    """The current user's own reminders for the event (of a series: for all its occurrences)."""
    event, _ = get_visible_event(event_id, request.user)
    return {"minutes": reminder_minutes(event, request.user)}


@router.put("/events/{event_id}/reminders", response=EventRemindersOut, auth=django_auth)
def put_reminders(request, event_id: str, payload: EventRemindersIn):
    # Everyone who sees an event may be reminded of it, viewers included; it concerns only them.
    event, _ = get_visible_event(event_id, request.user)
    return {"minutes": set_reminders(event, request.user, payload.minutes)}


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


def _serialize_participant(participant: EventParticipant) -> dict:
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


def _participant_event(event_id: str, user: User):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    membership = get_membership(event.calendar, user)
    if membership is None or not has_at_least_role(membership, Role.VIEWER):
        raise HttpError(403, "You cannot view this event")
    return event, membership


def _create_participant(event: Event, current_user: User, data):
    participant_status = data.status or "needs_action"
    if participant_status not in PARTICIPANT_STATUSES:
        raise HttpError(422, "Invalid participant status")
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


@router.get("/events/{event_id}/participants", response=list[EventParticipantOut], auth=django_auth)
def list_event_participants(request, event_id: str):
    event, _ = _participant_event(event_id, request.user)
    participants = EventParticipant.objects.filter(event=event).select_related("user").order_by("created_at")
    return [_serialize_participant(p) for p in participants]


@router.post("/events/{event_id}/participants", response=EventParticipantOut, auth=django_auth)
def add_event_participant(request, event_id: str, payload: EventParticipantCreate):
    event, membership = _participant_event(event_id, request.user)
    if not can_modify_event(event, str(request.user.id), membership.role):
        raise HttpError(403, "You cannot modify this event")
    participant = _create_participant(event, request.user, payload)
    return _serialize_participant(participant)


@router.patch("/events/{event_id}/participants/me", response=EventParticipantOut, auth=django_auth)
def update_my_participation(request, event_id: str, payload: EventParticipantUpdate):
    """Answers an invitation: sets the status of the current user's own participation."""
    try:
        participant = EventParticipant.objects.select_related("user").get(event_id=event_id, user=request.user)
    except EventParticipant.DoesNotExist:
        raise HttpError(404, "You are not a participant of this event")
    if payload.status is None or payload.status not in PARTICIPANT_STATUSES:
        raise HttpError(422, "Invalid participant status")
    participant.status = payload.status
    participant.save()
    return _serialize_participant(participant)


@router.patch("/events/{event_id}/participants/{participant_id}", response=EventParticipantOut, auth=django_auth)
def update_event_participant(request, event_id: str, participant_id: str, payload: EventParticipantUpdate):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    try:
        participant = EventParticipant.objects.get(id=participant_id, event=event)
    except EventParticipant.DoesNotExist:
        raise HttpError(404, "Participant not found")
    membership = get_membership(event.calendar, request.user)
    can_modify = membership is not None and can_modify_event(event, str(request.user.id), membership.role)
    if not (can_modify or str(participant.user_id) == str(request.user.id)):
        raise HttpError(403, "You cannot update this participant")
    if payload.status is None or payload.status not in PARTICIPANT_STATUSES:
        raise HttpError(422, "Invalid participant status")
    participant.status = payload.status
    participant.save()
    return _serialize_participant(participant)


@router.delete("/events/{event_id}/participants/{participant_id}", auth=django_auth)
def delete_event_participant(request, event_id: str, participant_id: str):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    try:
        participant = EventParticipant.objects.get(id=participant_id, event=event)
    except EventParticipant.DoesNotExist:
        raise HttpError(404, "Participant not found")
    membership = get_membership(event.calendar, request.user)
    can_modify = membership is not None and can_modify_event(event, str(request.user.id), membership.role)
    if not (can_modify or str(participant.user_id) == str(request.user.id)):
        raise HttpError(403, "You cannot remove this participant")
    participant.delete()
    return {"ok": True}
