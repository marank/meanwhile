"""
Calendar resource endpoints.
"""

from django.db import transaction
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from core.models import Resource, ResourceApprover
from core.models.base import Role
from core.schemas import (
    ApproverOut,
    ApproversIn,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from core.services.permissions import can_manage, get_member_calendar
from core.views.common import approvers_of, replace_approvers

router = Router()


@router.get("/calendars/{calendar_id}/resources", response=list[ResourceOut])
def list_resources(request, calendar_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user)
    return (
        Resource.objects.filter(calendar=calendar, archived_at__isnull=True)
        .prefetch_related("approvers__user")
        .order_by("name")
    )


@router.post("/calendars/{calendar_id}/resources", response=ResourceOut)
@transaction.atomic
def create_resource(request, calendar_id: str, payload: ResourceCreate):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    resource = Resource.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        # The schema still lets a null color through, which the column rejects.
        color=payload.color,  # type: ignore[misc]
        icon=payload.icon,
        requires_approval=payload.requires_approval,
        is_location=payload.is_location,
        is_active=payload.is_active,
    )
    return resource


@router.patch("/calendars/{calendar_id}/resources/{resource_id}", response=ResourceOut)
@transaction.atomic
def update_resource(request, calendar_id: str, resource_id: str, payload: ResourceUpdate):
    calendar, membership = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    data = payload.dict(exclude_unset=True)
    # Whether bookings need approval is the approvers' business, as are the approvers themselves.
    if "requires_approval" in data and data["requires_approval"] != resource.requires_approval:
        if not can_manage(membership):
            raise HttpError(403, "Only who manages the calendar can change whether bookings need approval")
    for attr, value in data.items():
        setattr(resource, attr, value)
    resource.save()
    return resource


@router.delete("/calendars/{calendar_id}/resources/{resource_id}")
def delete_resource(request, calendar_id: str, resource_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    # Archive instead of deleting so existing bookings keep their resource.
    Resource.objects.filter(id=resource_id, calendar=calendar).update(archived_at=timezone.now())
    return {"ok": True}


@router.get(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
)
def list_resource_approvers(request, calendar_id: str, resource_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    return approvers_of(ResourceApprover, resource=resource)


@router.put(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
)
@transaction.atomic
def set_resource_approvers(request, calendar_id: str, resource_id: str, payload: ApproversIn):
    """Sets the resource's own approvers; without any, the calendar's default approvers decide."""
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage approvers"
    )
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    replace_approvers(ResourceApprover, "resource", resource, calendar.id, payload.user_ids)
    return approvers_of(ResourceApprover, resource=resource)
