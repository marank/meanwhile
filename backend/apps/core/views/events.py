"""
Event and participant endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext
from ninja import Query, Router
from ninja.errors import HttpError

from apps.core.models import Calendar, Event, EventParticipant, User
from apps.core.models.base import EventStatus, Role, ShowAs
from apps.core.schemas import (
    EventCreate,
    EventDuplicate,
    EventOut,
    EventParticipantCreate,
    EventParticipantOut,
    EventParticipantUpdate,
    EventRemindersIn,
    EventRemindersOut,
    EventUpdate,
    OccurrenceOut,
    OccurrenceScope,
    OkOut,
)
from apps.core.services import duplicates, events, occurrences, participants
from apps.core.services.bookings import decidable_resources, is_in_approver_pool
from apps.core.services.itip import record_answer
from apps.core.services.permissions import (
    MembershipInfo,
    can_modify_event,
    get_member_calendar,
    get_membership,
    get_visible_event,
    memberships_of,
    participant_event_ids,
)
from apps.core.services.recurrence import as_utc, expand_events, is_series, recurrence_count
from apps.core.services.reminders import reminder_minutes, set_reminders
from apps.core.services.series import is_occurrence
from apps.core.views.common import AuthedRequest, serialize_event

router = Router()


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

    user_id = str(user.id)
    invited_to = participant_event_ids(user)
    can_decide: dict[tuple[object, ...], bool] = {}
    out = [
        OccurrenceOut(
            event_id=str(event.id),
            calendar_id=str(event.calendar_id),
            title=event.title,
            description=event.description,
            start=occ_start,
            end=occ_end,
            all_day=event.all_day,
            status=EventStatus(event.status),
            show_as=ShowAs(event.show_as),
            location=event.location,
            creator_id=str(event.creator_id),
            can_edit=can_modify_event(event, user_id, memberships[event.calendar_id].role),
            **_booking_fields(event),
            **_series_fields(event, occ_start),
        )
        for event, occ_start, occ_end in expand_events(events, range_start, range_end)
        if _is_listed(event, user_id, invited_to, can_decide)
    ]
    out.sort(key=lambda o: o.start)
    return out


def _is_listed(event: Event, user_id: str, invited_to: set[UUID], can_decide: dict[tuple[object, ...], bool]) -> bool:
    """Whether the user sees the event in the calendar; `can_decide` caches the approver checks
    across the events of one listing."""
    if str(event.creator_id) == user_id:
        return True
    if event.status in occurrences.GONE:
        return False
    if event.status != EventStatus.PENDING or event.id in invited_to:
        return True
    # Pending bookings are only shown to the requester, participants and approvers.
    # The pool is the same for the same bookings of a calendar (its owner always decides).
    key = (event.calendar_id, *sorted(str(i) for i in event.awaiting_approval or []))
    if key not in can_decide:
        can_decide[key] = is_in_approver_pool(event, user_id)
    return can_decide[key]


def _booking_fields(event: Event) -> dict[str, Any]:
    """The category, resource and location resource of an occurrence, by id with what the calendar
    shows of them; the related objects come with the listing's select_related."""
    category, resource, location_resource = event.category, event.resource, event.location_resource
    return {
        "category_id": str(event.category_id) if event.category_id else None,
        "category_name": category.name if category else None,
        "category_color": category.color if category else None,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "resource_name": resource.name if resource else None,
        "resource_icon": resource.icon if resource else "",
        "location_resource_id": str(event.location_resource_id) if event.location_resource_id else None,
        "location_resource_icon": location_resource.icon if location_resource else "",
    }


def _series_fields(event: Event, occ_start: datetime) -> dict[str, Any]:
    """How an occurrence belongs to a series: the series' id and the occurrence's original start,
    which a client sends back to change just this one."""
    series = is_series(event)
    belongs = series or bool(event.parent_id)
    if event.parent_id and event.recurrence_id:
        # A changed occurrence keeps the start it replaces, wherever it was moved to.
        recurrence_id: datetime | None = as_utc(event.recurrence_id)
    else:
        recurrence_id = occ_start if series else None
    return {
        "recurrence_count": recurrence_count(event, occ_start) if event.show_recurrence_count and series else None,
        "is_recurring": belongs,
        "series_id": str(event.parent_id or event.id) if belongs else None,
        "recurrence_id": recurrence_id,
    }


def _parse_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    range_start = as_utc(start)
    range_end = as_utc(end)
    if range_start >= range_end:
        raise HttpError(422, gettext("end must be after start"))
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
        calendar_id, request.user, Role.OWN, gettext("You do not have permission to create events")
    )
    with transaction.atomic():
        event = events.create_event(request.user, calendar, payload)
    return EventOut.model_validate(serialize_event(event))


@router.post("/events/{event_id}/duplicate", response=EventOut)
def duplicate_event(request: AuthedRequest, event_id: str, payload: EventDuplicate) -> EventOut:
    """A copy of the event at another time or in another calendar (one the user may add events to)."""
    source, _ = get_visible_event(event_id, request.user)
    calendar, _ = get_member_calendar(
        payload.calendar_id, request.user, Role.OWN, gettext("You do not have permission to create events")
    )
    with transaction.atomic():
        copy = duplicates.duplicate_event(
            request.user, source, calendar, payload.start, invite=payload.invite_participants
        )
    return EventOut.model_validate(serialize_event(copy))


@router.get("/events/{event_id}", response=EventOut)
def get_event(request: AuthedRequest, event_id: str) -> EventOut:
    event, _ = get_visible_event(event_id, request.user)
    data = serialize_event(event)
    data["can_decide"] = event.status == EventStatus.PENDING and bool(decidable_resources(event, str(request.user.id)))
    return EventOut.model_validate(data)


def _modifiable_event(event_id: str, user: User) -> tuple[Event, MembershipInfo]:
    event = Event.objects.select_related("calendar").get(id=event_id)
    membership = get_membership(event.calendar, user)
    if membership is None:
        raise HttpError(403, gettext("Not a member of this calendar"))
    if not can_modify_event(event, str(user.id), membership.role):
        raise HttpError(403, gettext("You do not have permission to edit this event"))
    return event, membership


@router.patch("/events/{event_id}", response=EventOut)
def update_event(request: AuthedRequest, event_id: str, payload: EventUpdate) -> EventOut:
    event, _ = _modifiable_event(event_id, request.user)
    data = payload.dict(exclude_unset=True)
    if event.parent_id and data.get("rrule"):
        raise HttpError(422, gettext("A changed occurrence of a series can't repeat itself"))
    with transaction.atomic():
        events.update_event(request.user, event, data)
    return EventOut.model_validate(serialize_event(event))


@router.delete("/events/{event_id}", response=OkOut)
def delete_event(request: AuthedRequest, event_id: str) -> dict[str, bool]:
    event, _ = _modifiable_event(event_id, request.user)
    occurrences.delete_event(event, request.user)
    return {"ok": True}


def _series_occurrence(event_id: str, user: User, recurrence_id: datetime) -> Event:
    series, _ = _modifiable_event(event_id, user)
    if not is_series(series) or series.parent_id:
        raise HttpError(422, gettext("This event is not a series"))
    if not is_occurrence(series, recurrence_id):
        raise HttpError(404, gettext("The series has no occurrence at that time"))
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
    changed = occurrences.change_occurrence(series, rid, request.user, payload.dict(exclude_unset=True), scope)
    return EventOut.model_validate(serialize_event(changed))


@router.delete("/events/{event_id}/occurrences/{recurrence_id}", response=OkOut)
def delete_occurrence(
    request: AuthedRequest, event_id: str, recurrence_id: datetime, scope: OccurrenceScope = "this"
) -> dict[str, bool]:
    """Removes one occurrence of a series ("this"), it and the later ones ("following"), or all."""
    rid = as_utc(recurrence_id)
    series = _series_occurrence(event_id, request.user, rid)
    occurrences.delete_occurrence(series, rid, request.user, scope)
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


@router.get("/events/{event_id}/participants", response=list[EventParticipantOut])
def list_event_participants(request: AuthedRequest, event_id: str) -> list[dict[str, Any]]:
    event, _ = _participant_event(event_id, request.user)
    participants = EventParticipant.objects.filter(event=event).select_related("user").order_by("created_at")
    return [_serialize_participant(p) for p in participants]


@router.post("/events/{event_id}/participants", response=EventParticipantOut)
def add_event_participant(request: AuthedRequest, event_id: str, payload: EventParticipantCreate) -> dict[str, Any]:
    event, membership = _participant_event(event_id, request.user)
    if not can_modify_event(event, str(request.user.id), membership.role):
        raise HttpError(403, gettext("You cannot modify this event"))
    return _serialize_participant(participants.invite(event, request.user, payload))


@router.patch("/events/{event_id}/participants/me", response=EventParticipantOut)
def update_my_participation(request: AuthedRequest, event_id: str, payload: EventParticipantUpdate) -> dict[str, Any]:
    """Answers an invitation: sets the status of the current user's own participation."""
    try:
        participant = EventParticipant.objects.select_related("user").get(event_id=event_id, user=request.user)
    except EventParticipant.DoesNotExist:
        raise HttpError(404, gettext("You are not a participant of this event")) from None
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
        raise HttpError(403, gettext("You cannot update this participant"))
    participants.set_status(participant, request.user, payload.status)
    return _serialize_participant(participant)


@router.delete("/events/{event_id}/participants/{participant_id}", response=OkOut)
def delete_event_participant(request: AuthedRequest, event_id: str, participant_id: str) -> dict[str, bool]:
    event = Event.objects.get(id=event_id)
    participant = EventParticipant.objects.get(id=participant_id, event=event)
    membership = get_membership(event.calendar, request.user)
    can_modify = membership is not None and can_modify_event(event, str(request.user.id), membership.role)
    if not (can_modify or participant.user_id == request.user.id):
        raise HttpError(403, gettext("You cannot remove this participant"))
    participants.remove(event, participant, request.user)
    return {"ok": True}
