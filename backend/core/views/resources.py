"""
Calendar resource endpoints.
"""

from django.db import transaction
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Calendar, Resource, ResourceApprover, User
from core.schemas import (
    ApproverCreate,
    ApproverOut,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from core.models.base import Role
from core.services.permissions import get_direct_membership, get_membership, has_at_least_role

router = CSRFRouter()


def _require_editor(user, calendar: Calendar):
    membership = get_membership(calendar, user)
    if membership is None or not has_at_least_role(membership, Role.EDITOR):
        raise HttpError(403, "Editor access required")


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


def _set_approvers(resource: Resource, user_ids: list[str]):
    """Replaces the resource's own approvers; each must be a direct member of the calendar."""
    for user_id in user_ids:
        if get_direct_membership(resource.calendar_id, user_id) is None:
            raise HttpError(400, "Approver must be a calendar member")
    ResourceApprover.objects.filter(resource=resource).exclude(user_id__in=user_ids).delete()
    for user in User.objects.filter(id__in=user_ids):
        ResourceApprover.objects.get_or_create(resource=resource, user=user)


@router.post("/calendars/{calendar_id}/resources", response=ResourceOut, auth=django_auth)
@transaction.atomic
def create_resource(request, calendar_id: str, payload: ResourceCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    resource = Resource.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        requires_approval=payload.requires_approval,
        is_active=payload.is_active,
    )
    _set_approvers(resource, payload.approver_ids)
    return resource


@router.patch("/calendars/{calendar_id}/resources/{resource_id}", response=ResourceOut, auth=django_auth)
@transaction.atomic
def update_resource(request, calendar_id: str, resource_id: str, payload: ResourceUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    data = payload.dict(exclude_unset=True)
    approver_ids = data.pop("approver_ids", None)
    for attr, value in data.items():
        setattr(resource, attr, value)
    resource.save()
    if approver_ids is not None:
        _set_approvers(resource, approver_ids)
    return resource


@router.delete("/calendars/{calendar_id}/resources/{resource_id}", auth=django_auth)
def delete_resource(request, calendar_id: str, resource_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
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
    _require_editor(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    return [
        ApproverOut(
            user_id=a.user_id,
            email=a.user.email,
            display_name=a.user.display_name,
        )
        for a in resource.approvers.select_related("user")
    ]


@router.post(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers",
    response=ApproverOut,
    auth=django_auth,
)
def add_resource_approver(request, calendar_id: str, resource_id: str, payload: ApproverCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    if get_direct_membership(calendar.id, payload.user_id) is None:
        raise HttpError(400, "Approver must be a calendar member")
    user = User.objects.get(id=payload.user_id)
    approver, _ = ResourceApprover.objects.get_or_create(resource=resource, user=user)
    return ApproverOut(
        user_id=approver.user_id,
        email=user.email,
        display_name=user.display_name,
    )


@router.delete(
    "/calendars/{calendar_id}/resources/{resource_id}/approvers/{user_id}",
    auth=django_auth,
)
def remove_resource_approver(request, calendar_id: str, resource_id: str, user_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    resource = Resource.objects.get(id=resource_id, calendar=calendar)
    ResourceApprover.objects.filter(resource=resource, user_id=user_id).delete()
    return {"ok": True}
