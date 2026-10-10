"""
Event and participant endpoints.
"""

from datetime import datetime, timezone

from django.db import transaction
from django.db.models import Q
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Calendar, Category, Event, EventParticipant, Resource, User
from core.models.base import EventStatus, Role
from core.schemas import (
    EventCreate,
    EventOut,
    EventParticipantCreate,
    EventParticipantInvite,
    EventParticipantOut,
    EventParticipantUpdate,
    EventUpdate,
    OccurrenceOut,
)
from core.services.activity import record_activity
from core.services.bookings import (
    can_decide_booking,
    can_modify_event,
    find_conflicting_approved_bookings,
    get_resource_approvers,
    initial_booking_status,
)
from core.services.ical import serialize_event_ical
from core.services.notifications import notify
from core.services.permissions import (
    get_membership,
    get_visible_event,
    has_at_least_role,
    participant_event_ids,
)
from core.services.recurrence import expand_events, make_aware, recurrence_count

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
        "start": make_aware(event.start),
        "end": make_aware(event.end),
        "all_day": event.all_day,
        "show_recurrence_count": event.show_recurrence_count,
        "rrule": event.rrule,
        "uid": event.uid,
        "category_id": str(event.category_id) if event.category_id else None,
        "category_name": event.category.name if event.category else None,
        "category_color": event.category.color if event.category else None,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "resource_name": event.resource.name if event.resource else None,
        "status": event.status,
        "decided_by": str(event.decided_by_id) if event.decided_by_id else None,
        "decided_at": event.decided_at,
        "decision_note": event.decision_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


@router.get("/calendars/{calendar_id}/events", response=list[OccurrenceOut], auth=django_auth)
def list_events(request, calendar_id: str, start: datetime, end: datetime):
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    range_start = make_aware(start)
    range_end = make_aware(end)
    if range_start >= range_end:
        raise HttpError(422, "end must be after start")

    events = Event.objects.filter(
        Q(calendar=calendar),
        Q(start__lt=range_end),
        Q(rrule__isnull=False) | Q(all_day=True) | Q(end__gt=range_start),
    ).select_related("calendar", "category", "resource")

    hidden = {EventStatus.REJECTED, EventStatus.CANCELLED}
    user_id = str(request.user.id)
    invited_to = participant_event_ids(request.user)
    can_decide_by_resource: dict[str | None, bool] = {}
    out = []
    for event, occ_start, occ_end in expand_events(events, range_start, range_end):
        if event.status in hidden and str(event.creator_id) != user_id:
            continue
        if event.status == EventStatus.PENDING and str(event.creator_id) != user_id and event.id not in invited_to:
            # Pending bookings are only shown to the requester, participants and approvers.
            if event.resource_id not in can_decide_by_resource:
                can_decide_by_resource[event.resource_id] = can_decide_booking(calendar, event.resource, user_id)
            if not can_decide_by_resource[event.resource_id]:
                continue
        out.append(OccurrenceOut(
            event_id=str(event.id),
            title=event.title,
            description=event.description,
            start=occ_start,
            end=occ_end,
            all_day=event.all_day,
            recurrence_count=(
                recurrence_count(event, occ_start)
                if event.show_recurrence_count and event.rrule
                else None
            ),
            status=event.status,
            color=event.calendar.color,
            dark_color=event.calendar.dark_color,
            category_id=str(event.category_id) if event.category_id else None,
            category_name=event.category.name if event.category else None,
            category_color=event.category.color if event.category else None,
            resource_id=str(event.resource_id) if event.resource_id else None,
            resource_name=event.resource.name if event.resource else None,
            creator_id=str(event.creator_id),
            can_edit=can_modify_event(event, str(request.user.id), membership.role),
            is_recurring=bool(event.rrule),
        ))
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

    resource = None
    if payload.resource_id:
        resource = Resource.objects.filter(
            id=payload.resource_id, calendar=calendar, is_active=True, archived_at__isnull=True
        ).first()
        if resource is None:
            raise HttpError(404, "Resource not found")

    with transaction.atomic():
        event = Event.objects.create(
            calendar=calendar,
            creator=request.user,
            title=payload.title if payload.title is not None else "",
            description=payload.description,
            start=start,
            end=end,
            all_day=payload.all_day,
            show_recurrence_count=payload.show_recurrence_count,
            rrule=payload.rrule,
            category=category,
            resource=resource,
            uid="",
            status=initial_booking_status(resource, str(request.user.id)),
        )
        if event.status == EventStatus.APPROVED:
            # Booked by someone who may approve it: the approval step is skipped.
            event.decided_by = request.user
            event.decided_at = datetime.now(timezone.utc)
        event.uid = str(event.id)
        event.save()

        if resource:
            conflicts = find_conflicting_approved_bookings(resource, event)
            if conflicts:
                raise HttpError(
                    409,
                    {
                        "message": "This booking conflicts with an approved booking",
                        "conflicts": [str(c.id) for c in conflicts],
                    },
                )

        event.raw_ical = serialize_event_ical(event)
        event.save()
        record_activity(event, str(request.user.id), "created")
        if payload.participants:
            for invite in payload.participants:
                _create_participant(event, request.user, invite)
        if event.status == EventStatus.PENDING and resource is not None:
            notify(
                [str(a.id) for a in get_resource_approvers(resource)] + [str(calendar.owner_id)],
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
    data["can_decide"] = event.status == EventStatus.PENDING and can_decide_booking(
        event.calendar, event.resource, str(request.user.id)
    )
    return EventOut.model_validate(data)


@router.patch("/events/{event_id}", response=EventOut, auth=django_auth)
def update_event(request, event_id: str, payload: EventUpdate):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    calendar = event.calendar
    membership = get_membership(calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not can_modify_event(event, str(request.user.id), membership.role):
        raise HttpError(403, "You do not have permission to edit this event")
    if calendar.force_all_day and payload.all_day is False:
        raise HttpError(422, "This calendar only allows all-day events")

    old_status = event.status
    old_values = {
        "title": event.title,
        "description": event.description,
        "start": make_aware(event.start),
        "end": make_aware(event.end),
        "all_day": event.all_day,
        "rrule": event.rrule,
        "category": event.category_id,
        "resource": event.resource_id,
        "show_recurrence_count": event.show_recurrence_count,
    }

    data = payload.dict(exclude_unset=True)
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
        if not data["resource_id"]:
            resource = None
        else:
            resource = Resource.objects.filter(
                id=data["resource_id"], calendar=calendar, is_active=True, archived_at__isnull=True
            ).first()
            if resource is None:
                raise HttpError(404, "Resource not found")

    if "title" in data:
        event.title = data["title"] or ""
    if "description" in data:
        event.description = data["description"]
    if "start" in data:
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
    resource_changed = (resource.id if resource else None) != old_values["resource"]

    with transaction.atomic():
        if resource_changed:
            event.resource_id = resource.id if resource else None
            event.status = initial_booking_status(resource, str(request.user.id))
            self_approved = event.status == EventStatus.APPROVED
            event.decided_by = request.user if self_approved else None
            event.decided_at = datetime.now(timezone.utc) if self_approved else None
            event.decision_note = None
        elif (
            rescheduled
            and resource is not None
            and resource.requires_approval
            and event.status in {EventStatus.APPROVED, EventStatus.CONFIRMED}
            # A change made by someone who may approve the booking keeps it approved.
            and not can_decide_booking(calendar, resource, str(request.user.id))
        ):
            event.status = EventStatus.PENDING
            event.decided_by = None
            event.decided_at = None
            event.decision_note = None

        if resource:
            conflicts = find_conflicting_approved_bookings(resource, event)
            if conflicts:
                raise HttpError(
                    409,
                    {
                        "message": "This booking conflicts with an approved booking",
                        "conflicts": [str(c.id) for c in conflicts],
                    },
                )

        changed = []
        for field, attr in (
            ("title", "title"),
            ("description", "description"),
            ("start", "start"),
            ("end", "end"),
            ("all_day", "all_day"),
            ("rrule", "rrule"),
            ("category", "category_id"),
            ("resource", "resource_id"),
            ("show_recurrence_count", "show_recurrence_count"),
        ):
            value = getattr(event, attr)
            if attr in ("start", "end"):
                value = make_aware(value)
            if value != old_values[field]:
                changed.append(field)

        event.raw_ical = serialize_event_ical(event)
        event.save()
        status_reset = (
            event.status == EventStatus.PENDING and old_status != EventStatus.PENDING
        )
        if changed:
            details = {"fields": changed}
            if status_reset:
                details["status"] = "pending"
            record_activity(event, str(request.user.id), "updated", details)
        if status_reset and resource is not None:
            notify(
                [str(a.id) for a in get_resource_approvers(resource)] + [str(calendar.owner_id)],
                "approval_requested",
                str(request.user.id),
                event.title,
                calendar_id=str(calendar.id),
                event_id=str(event.id),
            )

    return EventOut.model_validate(_serialize_event(event))


@router.delete("/events/{event_id}", auth=django_auth)
def delete_event(request, event_id: str):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    membership = get_membership(event.calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not can_modify_event(event, str(request.user.id), membership.role):
        raise HttpError(403, "You do not have permission to delete this event")
    event.delete()
    return {"ok": True}


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
