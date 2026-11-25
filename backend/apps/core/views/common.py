"""
Common view helpers.
"""

from typing import Any

from django.http import HttpRequest
from django.utils.translation import gettext
from ninja.errors import HttpError

from apps.core.models import CalendarApprover, Event, ResourceApprover, User
from apps.core.schemas import ApproverOut
from apps.core.services.bookings import awaiting_resources
from apps.core.services.recurrence import as_utc


class AuthedRequest(HttpRequest):
    """The request of a signed-in user, as every endpoint gets that doesn't say `auth=None` (apps.core.api)."""

    user: User


def require_admin(request: AuthedRequest) -> None:
    # Signed in, as every endpoint requires (apps.core.api).
    if not request.user.is_admin:
        raise HttpError(403, gettext("Admin access required"))


def approvers_of(approver_model: type[CalendarApprover] | type[ResourceApprover], **owner: object) -> list[ApproverOut]:
    """The approvers of a calendar or resource (`approver_model` filtered by `owner`), by name."""
    rows = approver_model.objects.filter(**owner).select_related("user").order_by("user__display_name", "user__email")
    return [ApproverOut(user_id=str(a.user_id), email=a.user.email, display_name=a.user.display_name) for a in rows]


def serialize_event(event: Event) -> dict[str, Any]:
    """An event as EventOut (and ApprovalOut, which adds to it) shows it."""
    return {
        "id": event.id,
        "calendar_id": str(event.calendar_id),
        "creator_id": str(event.creator_id),
        "creator_name": event.creator.display_name,
        "creator_email": event.creator.email,
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
        "show_as": event.show_as,
        "awaiting_approval": [r.name for r in awaiting_resources(event)],
        "decided_by": str(event.decided_by_id) if event.decided_by_id else None,
        "decided_at": event.decided_at,
        "decision_note": event.decision_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
