"""
Approval workflow endpoints.
"""

from datetime import datetime, timezone

from django.db.models import Q
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import CalendarApprover, Event, Resource, ResourceApprover
from core.models.base import EventStatus, Role
from core.schemas import ApprovalAction, ApprovalOut, ApproverOut
from core.services.activity import record_activity
from core.services.bookings import (
    find_conflicting_approved_bookings,
    get_resource_approvers,
    is_in_approver_pool,
)
from core.services.notifications import notify
from core.services.permissions import get_membership, has_at_least_role
from core.services.recurrence import make_aware

router = CSRFRouter()


def _approval_recipients(event: Event):
    recipients = []
    if event.resource is not None:
        recipients += [str(a.id) for a in get_resource_approvers(event.resource)]
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


def _serialize_approval(event: Event) -> dict:
    data = _serialize_event(event)
    data["approver_pool"] = [
        ApproverOut(
            user_id=str(a.id),
            email=a.email,
            display_name=a.display_name,
        )
        for a in (get_resource_approvers(event.resource) if event.resource else [])
    ]
    return data


@router.get("/approvals", response=list[ApprovalOut], auth=django_auth)
def list_pending_approvals(request):
    user = request.user
    pending = (
        Event.objects.filter(
            status=EventStatus.PENDING,
            resource__isnull=False,
        )
        .filter(
            Q(calendar__owner=user)
            | Q(resource__approvers__user=user)
            | Q(calendar__approvers__user=user)
        )
        .select_related("calendar", "category", "resource")
        .prefetch_related("resource__approvers", "resource__approvers__user")
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
    if not is_in_approver_pool(event, user=request.user):
        raise HttpError(403, "You cannot approve this booking")

    if event.resource is not None:
        conflicts = find_conflicting_approved_bookings(event.resource, event)
        if conflicts:
            raise HttpError(
                409,
                {
                    "message": "Approval conflicts with an existing approved booking",
                    "conflicts": [str(c.id) for c in conflicts],
                },
            )

    event.status = EventStatus.APPROVED
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = payload.note
    event.save()
    record_activity(
        event,
        str(request.user.id),
        "approved",
        {"note": payload.note} if payload.note else None,
    )
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

    event.status = EventStatus.REJECTED
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = payload.note
    event.save()
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
        and event.resource is not None
    )
    event.status = EventStatus.CANCELLED
    event.decided_by = request.user
    event.decided_at = datetime.now(timezone.utc)
    event.save()
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
