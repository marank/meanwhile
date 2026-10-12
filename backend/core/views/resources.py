"""
Calendar resource endpoints.
"""

from django.db import transaction
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Calendar, Resource, ResourceApprover
from core.schemas import (
    ApproverOut,
    ApproversIn,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from core.models.base import Role
from core.services.permissions import get_membership, has_at_least_role
from core.views.common import approvers_of, replace_approvers

router = CSRFRouter()


def _require_full_access(user, calendar: Calendar):
    membership = get_membership(calendar, user)
    if membership is None or not has_at_least_role(membership, Role.FULL):
        raise HttpError(403, "Full access required")


@router.get("/calendars/{calendar_id}/resources", response=list[ResourceOut], auth=django_auth)
def list_resources(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    if get_membership(calendar, request.user) is None and not calendar.is_public:
        raise HttpError(403, "Not a member of this calendar")
    return (
        Resource.objects.filter(calendar=calendar, archived_at__isnull=True)
        .prefetch_related("approvers__user")
        .order_by("name")
    )


@router.post("/calendars/{calendar_id}/resources", response=ResourceOut, auth=django_auth)
@transaction.atomic
def create_resource(request, calendar_id: str, payload: ResourceCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_full_access(request.user, calendar)
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


@router.patch("/calendars/{calendar_id}/resources/{resource_id}", response=ResourceOut, auth=django_auth)
@transaction.atomic
def update_resource(request, calendar_id: str, resource_id: str, payload: ResourceUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_full_access(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    data = payload.dict(exclude_unset=True)
    for attr, value in data.items():
        setattr(resource, attr, value)
    resource.save()
    return resource


@router.delete("/calendars/{calendar_id}/resources/{resource_id}", auth=django_auth)
def delete_resource(request, calendar_id: str, resource_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_full_access(request.user, calendar)
    # Archive instead of deleting so existing bookings keep their resource.
    Resource.objects.filter(id=resource_id, calendar=calendar).update(archived_at=timezone.now())
    return {"ok": True}


@router.get(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
    auth=django_auth,
)
def list_resource_approvers(request, calendar_id: str, resource_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_full_access(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    return approvers_of(ResourceApprover, resource=resource)


@router.put(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=list[ApproverOut],
    auth=django_auth,
)
@transaction.atomic
def set_resource_approvers(request, calendar_id: str, resource_id: str, payload: ApproversIn):
    """Sets the resource's own approvers; without any, the calendar's default approvers decide."""
    calendar = Calendar.objects.get(id=calendar_id)
    _require_full_access(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    replace_approvers(ResourceApprover, "resource", resource, calendar.id, payload.user_ids)
    return approvers_of(ResourceApprover, resource=resource)
