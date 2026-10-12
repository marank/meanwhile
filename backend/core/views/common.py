"""
Common view helpers.
"""

from ninja.errors import HttpError

from core.models import Event, User
from core.schemas import ApproverOut
from core.services.bookings import awaiting_resources
from core.services.permissions import get_direct_membership
from core.services.recurrence import as_utc


def require_admin(request):
    # Signed in, as every endpoint requires (core.api).
    if not request.user.is_admin:
        raise HttpError(403, "Admin access required")


def approvers_of(approver_model, **owner) -> list[ApproverOut]:
    """The approvers of a calendar or resource (`approver_model` filtered by `owner`), by name."""
    rows = approver_model.objects.filter(**owner).select_related("user").order_by("user__display_name", "user__email")
    return [ApproverOut(user_id=a.user_id, email=a.user.email, display_name=a.user.display_name) for a in rows]


def replace_approvers(approver_model, owner_field: str, owner, calendar_id, user_ids: list[str]) -> None:
    """Makes `user_ids` the approvers of the owner (a calendar or resource); each must be a direct member."""
    wanted = list(dict.fromkeys(user_ids))
    for user_id in wanted:
        if get_direct_membership(calendar_id, user_id) is None:
            raise HttpError(400, "Approver must be a calendar member")
    current = approver_model.objects.filter(**{owner_field: owner})
    current.exclude(user_id__in=wanted).delete()
    missing = set(wanted) - set(current.values_list("user_id", flat=True))
    approver_model.objects.bulk_create(
        [approver_model(**{owner_field: owner, "user": user}) for user in User.objects.filter(id__in=missing)]
    )


def serialize_event(event: Event) -> dict:
    """An event as EventOut (and ApprovalOut, which adds to it) shows it."""
    return {
        "id": event.id,
        "calendar_id": str(event.calendar_id),
        "creator_id": str(event.creator_id),
        "creator_name": event.creator_name,
        "creator_email": event.creator_email,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "location_resource_id": str(event.location_resource_id) if event.location_resource_id else None,
        "location_resource_name": event.location_resource.name if event.location_resource else None,
        "start": as_utc(event.start),
        "end": as_utc(event.end),
        "all_day": event.all_day,
        "timezone": event.timezone,
        "show_recurrence_count": event.show_recurrence_count,
        "rrule": event.rrule,
        "rdates": event.rdates or [],
        "uid": event.uid,
        "parent_id": str(event.parent_id) if event.parent_id else None,
        "recurrence_id": as_utc(event.recurrence_id) if event.recurrence_id else None,
        "category_id": str(event.category_id) if event.category_id else None,
        "category_name": event.category.name if event.category else None,
        "category_color": event.category.color if event.category else None,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "resource_name": event.resource.name if event.resource else None,
        "status": event.status,
        "awaiting_approval": [r.name for r in awaiting_resources(event)],
        "decided_by": str(event.decided_by_id) if event.decided_by_id else None,
        "decided_at": event.decided_at,
        "decision_note": event.decision_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
