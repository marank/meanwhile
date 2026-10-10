"""
Resource booking approval/conflict logic.
"""

from datetime import datetime, timedelta

from django.db import transaction

from core.models.base import EventStatus, Role
from core.models.calendars import CalendarApprover
from core.models.events import Event
from core.models.resources import Resource
from core.models.users import User
from core.services.recurrence import find_conflicts, make_aware


def get_resource_approvers(resource: Resource):
    """The resource's own approvers, else the calendar's default approvers; may be empty.

    The calendar owner can always decide regardless (see is_in_approver_pool).
    """
    resource_approvers = [a.user for a in resource.approvers.all()]
    if resource_approvers:
        return resource_approvers
    return [
        a.user
        for a in CalendarApprover.objects.filter(calendar=resource.calendar).select_related("user")
    ]


def can_decide_booking(calendar, resource: Resource | None, user_id: str) -> bool:
    """The calendar owner and the resource's approver pool may approve or reject bookings."""
    if str(calendar.owner_id) == str(user_id):
        return True
    if resource is None:
        return False
    return any(str(a.id) == str(user_id) for a in get_resource_approvers(resource))


def is_in_approver_pool(event: Event, user: User | None = None, user_id: str | None = None) -> bool:
    if user_id is None and user is not None:
        user_id = str(user.id)
    if user_id is None:
        return False
    return can_decide_booking(event.calendar, event.resource, user_id)


def initial_booking_status(resource: Resource | None, user_id: str | None = None) -> str:
    """Status of a new booking; someone who may approve it doesn't have to ask themselves."""
    if resource is None or not resource.requires_approval:
        return EventStatus.CONFIRMED
    if user_id is not None and can_decide_booking(resource.calendar, resource, user_id):
        return EventStatus.APPROVED
    return EventStatus.PENDING


def find_conflicting_approved_bookings(resource: Resource, event: Event):
    with transaction.atomic():
        # Serialize concurrent approvals on the same resource.
        Resource.objects.select_for_update().get(pk=resource.pk)

        horizon = max(make_aware(event.end), make_aware(event.start) + timedelta(days=730))
        approved = Event.objects.filter(
            resource=resource,
            status__in={EventStatus.APPROVED, EventStatus.CONFIRMED},
            start__lt=horizon,
        ).exclude(pk=event.pk)
        return find_conflicts(event, approved, horizon)


def can_modify_event(event: Event, user_id: str, role: str) -> bool:
    return role in {Role.OWNER, Role.EDITOR} or str(event.creator_id) == str(user_id)
