"""
Approval workflow endpoints.
"""

from datetime import datetime, timezone

from django.db.models import Q
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Event
from core.models.base import EventStatus, Role
from core.schemas import ApprovalAction, ApprovalOut, ApproverOut
from core.services.activity import record_activity
from core.services.bookings import (
    approvers_of,
    awaiting_resources,
    booked_resources,
    decidable_resources,
    find_booking_conflicts,
    is_in_approver_pool,
)
from core.services.notifications import notify
from core.services.permissions import get_membership, has_at_least_role
from core.services.recurrence import make_aware

router = CSRFRouter()


def _approval_recipients(event: Event):
    recipients = [str(a.id) for a in approvers_of(booked_resources(event))]
    recipients.append(str(event.calendar.owner_id))
    return recipients


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
        "timezone": event.timezone,
        "show_recurrence_count": event.show_recurrence_count,
        "rrule": event.rrule,
        "uid": event.uid,
        "category_id": str(event.category_id) if event.category_id else None,
        "category_name": event.category.name if event.category else None,
        "category_color": event.category.color if event.category else None,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "resource_name": event.resource.name if event.resource else None,
        "location": event.location,
        "location_resource_id": str(event.location_resource_id) if event.location_resource_id else None,
        "location_resource_name": event.location_resource.name if event.location_resource else None,
        "status": event.status,
        "awaiting_approval": [r.name for r in awaiting_resources(event)],
        "decided_by": str(event.decided_by_id) if event.decided_by_id else None,
        "decided_at": event.decided_at,
        "decision_note": event.decision_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def _serialize_approval(event: Event) -> dict:
    data = _serialize_event(event)
    data["approver_pool"] = [
        ApproverOut(
            user_id=str(a.id),
            email=a.email,
            display_name=a.display_name,
        )
        for a in approvers_of(awaiting_resources(event))
    ]
    return data


@router.get("/approvals", response=list[ApprovalOut], auth=django_auth)
def list_pending_approvals(request):
    user = request.user
    pending = (
        Event.objects.filter(status=EventStatus.PENDING)
        .filter(Q(resource__isnull=False) | Q(location_resource__isnull=False))
        .filter(
            Q(calendar__owner=user)
            | Q(resource__approvers__user=user)
            | Q(location_resource__approvers__user=user)
            | Q(calendar__approvers__user=user)
        )
        .select_related("calendar", "category", "resource", "location_resource")
        .distinct()
    )
    result = []
    for event in pending:
        if is_in_approver_pool(event, user=user):
            result.append(ApprovalOut.model_validate(_serialize_approval(event)))
    return result


@router.post("/events/{event_id}/approve", response=ApprovalOut, auth=django_auth)
def approve_event(request, event_id: str, payload: ApprovalAction):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    if event.status != EventStatus.PENDING:
        raise HttpError(400, "Event is not pending")
    membership = get_membership(event.calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    # Each approver approves the bookings they are responsible for (e.g. the room or the projector);
    # the event is approved once none is left.
    decided = decidable_resources(event, str(request.user.id))
    if not decided:
        raise HttpError(403, "You cannot approve this booking")
    decided_ids = {str(r.pk) for r in decided}
    remaining = [i for i in event.awaiting_approval or [] if str(i) not in decided_ids]

    if not remaining:
        conflicts = find_booking_conflicts(event)
        # Changed occurrences waiting along with the series are approved with it.
        for occurrence in event.overrides.filter(status=event.status):
            conflicts += find_booking_conflicts(occurrence)
        if conflicts:
            raise HttpError(
                409,
                {
                    "message": "Approval conflicts with an existing approved booking",
                    "conflicts": [str(c.id) for c in conflicts],
                },
            )

    previous_status = event.status
    event.awaiting_approval = remaining
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = payload.note
    if not remaining:
        event.status = EventStatus.APPROVED
    event.save()
    _decide_changed_occurrences(event, previous_status, decided_ids)
    details = {"resources": sorted(r.name for r in decided)}
    if payload.note:
        details["note"] = payload.note
    record_activity(event, str(request.user.id), "approved", details)
    if remaining:
        return ApprovalOut.model_validate(_serialize_approval(event))
    notify(
        [str(event.creator_id)],
        "booking_approved",
        str(request.user.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"note": payload.note} if payload.note else None,
    )
    return ApprovalOut.model_validate(_serialize_approval(event))


def _decide_changed_occurrences(series: Event, previous_status: str, decided_ids: set[str] | None = None) -> None:
    # Changed occurrences that shared the series' status follow its decision.
    for occurrence in series.overrides.filter(status=previous_status):
        awaiting = [i for i in occurrence.awaiting_approval or [] if decided_ids is not None and str(i) not in decided_ids]
        if decided_ids is not None and awaiting:
            occurrence.awaiting_approval = awaiting
        else:
            occurrence.status = series.status if decided_ids is None else EventStatus.APPROVED
            occurrence.awaiting_approval = []
        occurrence.decided_by = series.decided_by
        occurrence.decided_at = series.decided_at
        occurrence.decision_note = series.decision_note
        occurrence.save()


@router.post("/events/{event_id}/reject", response=ApprovalOut, auth=django_auth)
def reject_event(request, event_id: str, payload: ApprovalAction):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    if event.status != EventStatus.PENDING:
        raise HttpError(400, "Event is not pending")
    if get_membership(event.calendar, request.user) is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_in_approver_pool(event, user=request.user):
        raise HttpError(403, "You cannot reject this booking")

    previous_status = event.status
    event.status = EventStatus.REJECTED
    event.awaiting_approval = []
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = payload.note
    event.save()
    _decide_changed_occurrences(event, previous_status)
    record_activity(
        event,
        str(request.user.id),
        "rejected",
        {"note": payload.note} if payload.note else None,
    )
    notify(
        [str(event.creator_id)],
        "booking_rejected",
        str(request.user.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"note": payload.note} if payload.note else None,
    )
    return ApprovalOut.model_validate(_serialize_approval(event))


@router.post("/events/{event_id}/cancel", response=ApprovalOut, auth=django_auth)
def cancel_event(request, event_id: str):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")
    membership = get_membership(event.calendar, request.user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if str(event.creator_id) != str(request.user.id) and not has_at_least_role(membership, Role.EDITOR):
        raise HttpError(403, "You cannot cancel this event")

    had_booking = (
        event.status in {EventStatus.PENDING, EventStatus.APPROVED}
        and bool(booked_resources(event))
    )
    previous_status = event.status
    event.status = EventStatus.CANCELLED
    event.awaiting_approval = []
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.save()
    _decide_changed_occurrences(event, previous_status)
    record_activity(event, str(request.user.id), "cancelled")
    if had_booking:
        notify(
            _approval_recipients(event),
            "booking_cancelled",
            str(request.user.id),
            event.title,
            calendar_id=str(event.calendar_id),
            event_id=str(event.id),
        )
    return ApprovalOut.model_validate(_serialize_approval(event))
