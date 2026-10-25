"""
Calendar resource endpoints.
"""

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from core.models import Resource, ResourceApprover
from core.models.base import Role
from core.schemas import (
    ApproverOut,
    ApproversIn,
    OkOut,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from core.services.permissions import can_manage, get_member_calendar
from core.views.common import AuthedRequest, approvers_of, replace_approvers

router = Router()


@router.get("/calendars/{calendar_id}/resources", response=list[ResourceOut])
def list_resources(request: AuthedRequest, calendar_id: str) -> QuerySet[Resource]:
    calendar, _ = get_member_calendar(calendar_id, request.user)
    return (
        Resource.objects.filter(calendar=calendar, archived_at__isnull=True)
        .prefetch_related("approvers__user")
        .order_by("name")
    )


@router.post("/calendars/{calendar_id}/resources", response=ResourceOut)
@transaction.atomic
def create_resource(request: AuthedRequest, calendar_id: str, payload: ResourceCreate) -> Resource:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    resource = Resource.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
        requires_approval=payload.requires_approval,
        is_location=payload.is_location,
        is_active=payload.is_active,
    )
    return resource


@router.patch("/calendars/{calendar_id}/resources/{resource_id}", response=ResourceOut)
@transaction.atomic
def update_resource(request: AuthedRequest, calendar_id: str, resource_id: str, payload: ResourceUpdate) -> Resource:
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


@router.delete("/calendars/{calendar_id}/resources/{resource_id}", response=OkOut)
def delete_resource(request: AuthedRequest, calendar_id: str, resource_id: str) -> dict[str, bool]:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    # Archive instead of deleting so existing bookings keep their resource.
    Resource.objects.filter(id=resource_id, calendar=calendar).update(archived_at=timezone.now())
    return {"ok": True}


@router.get(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
)
def list_resource_approvers(request: AuthedRequest, calendar_id: str, resource_id: str) -> list[ApproverOut]:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    return approvers_of(ResourceApprover, resource=resource)


@router.put(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
)
@transaction.atomic
def set_resource_approvers(
    request: AuthedRequest, calendar_id: str, resource_id: str, payload: ApproversIn
) -> list[ApproverOut]:
    """Sets the resource's own approvers; without any, the calendar's default approvers decide."""
    calendar, _ = get_member_calendar(
        calendar_id, request.user, Role.MANAGE, "Only who manages the calendar can manage approvers"
    )
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    replace_approvers(ResourceApprover, "resource", resource, calendar.id, payload.user_ids)
    return approvers_of(ResourceApprover, resource=resource)
