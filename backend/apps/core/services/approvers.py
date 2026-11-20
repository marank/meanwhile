"""
Who decides on bookings: a calendar's default approvers and a resource's own.
"""

from uuid import UUID

from ninja.errors import HttpError

from apps.core.models import Calendar, CalendarApprover, Resource, ResourceApprover, User, as_uuid
from apps.core.models.base import AnyId
from apps.core.services.permissions import get_direct_membership


def replace_approvers[A: (CalendarApprover, ResourceApprover)](
    approver_model: type[A],
    owner_field: str,
    owner: Calendar | Resource,
    calendar_id: AnyId,
    user_ids: list[str],
) -> None:
    """Makes `user_ids` the approvers of the owner (a calendar or resource); each must be a direct member."""
    wanted: list[UUID] = []
    for user_id in dict.fromkeys(as_uuid(user_id) for user_id in user_ids):
        if user_id is None or get_direct_membership(calendar_id, user_id) is None:
            raise HttpError(400, "Approver must be a calendar member")
        wanted.append(user_id)
    current = approver_model.objects.filter(**{owner_field: owner})
    current.exclude(user_id__in=wanted).delete()
    missing = set(wanted) - set(current.values_list("user_id", flat=True))
    approver_model.objects.bulk_create(
        [approver_model(**{owner_field: owner, "user": user}) for user in User.objects.filter(id__in=missing)]
    )
