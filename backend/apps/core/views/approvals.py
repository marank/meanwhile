"""
Approval workflow endpoints.
"""

from typing import Any

from django.db.models import Prefetch, Q
from ninja import Router

from apps.core.models import CalendarApprover, Event, ResourceApprover
from apps.core.models.base import EventStatus
from apps.core.schemas import ApprovalAction, ApprovalOut, ApproverOut
from apps.core.services import approvals
from apps.core.services.bookings import approvers_of, awaiting_resources, is_in_approver_pool
from apps.core.views.common import AuthedRequest, serialize_event

router = Router()


def _serialize_approval(event: Event) -> dict[str, Any]:
    data = serialize_event(event)
    data["approver_pool"] = [
        ApproverOut(
            user_id=str(a.id),
            email=a.email,
            display_name=a.display_name,
        )
        for a in approvers_of(awaiting_resources(event))
    ]
    return data


@router.get("/approvals", response=list[ApprovalOut])
def list_pending_approvals(request: AuthedRequest) -> list[ApprovalOut]:
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
        .select_related("calendar", "category", "creator", "resource", "location_resource")
        # Who may decide on each booking, for all events at once (bookings.get_resource_approvers).
        .prefetch_related(
            Prefetch("resource__approvers", queryset=ResourceApprover.objects.select_related("user")),
            Prefetch("location_resource__approvers", queryset=ResourceApprover.objects.select_related("user")),
            Prefetch("resource__calendar__approvers", queryset=CalendarApprover.objects.select_related("user")),
            Prefetch(
                "location_resource__calendar__approvers", queryset=CalendarApprover.objects.select_related("user")
            ),
        )
        .distinct()
    )
    result: list[ApprovalOut] = []
    for event in pending:
        if is_in_approver_pool(event, user.id):
            result.append(ApprovalOut.model_validate(_serialize_approval(event)))
    return result


@router.post("/events/{event_id}/approve", response=ApprovalOut)
def approve_event(request: AuthedRequest, event_id: str, payload: ApprovalAction) -> ApprovalOut:
    return ApprovalOut.model_validate(_serialize_approval(approvals.approve(event_id, request.user, payload.note)))


@router.post("/events/{event_id}/reject", response=ApprovalOut)
def reject_event(request: AuthedRequest, event_id: str, payload: ApprovalAction) -> ApprovalOut:
    return ApprovalOut.model_validate(_serialize_approval(approvals.reject(event_id, request.user, payload.note)))


@router.post("/events/{event_id}/cancel", response=ApprovalOut)
def cancel_event(request: AuthedRequest, event_id: str) -> ApprovalOut:
    return ApprovalOut.model_validate(_serialize_approval(approvals.cancel(event_id, request.user)))
