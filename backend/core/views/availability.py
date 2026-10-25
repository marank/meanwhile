"""
Availability endpoint: when people and resources are taken, for planning an event.
"""

from datetime import timedelta
from typing import Any

from ninja import Router
from ninja.errors import HttpError

from core.models import Resource, User
from core.schemas import AvailabilityIn, AvailabilityOut
from core.services.availability import resource_periods, user_periods
from core.services.permissions import get_membership
from core.services.recurrence import as_utc
from core.views.common import AuthedRequest

router = Router()

MAX_RANGE = timedelta(days=62)


@router.post("/availability", response=AvailabilityOut)
def availability(request: AuthedRequest, data: AvailabilityIn) -> dict[str, Any]:
    """Busy periods only, no titles or details. Users can be looked up by anyone signed in, as in
    the user search; resources only by members of their calendar. A POST, though it changes nothing:
    see AvailabilityIn."""
    start, end = as_utc(data.start), as_utc(data.end)
    user_ids, resource_ids, exclude_event_id = data.user_ids, data.resource_ids, data.exclude_event_id
    if not start < end <= start + MAX_RANGE:
        raise HttpError(422, "end must be after start and at most 62 days later")
    users = User.objects.filter(id__in=user_ids, is_active=True).order_by("display_name")
    resources = [
        r
        for r in Resource.objects.filter(id__in=resource_ids).select_related("calendar").order_by("name")
        if get_membership(r.calendar, request.user) is not None
    ]
    return {
        "users": [
            {"id": u.id, "name": u.display_name or u.email, "busy": user_periods(u, start, end, exclude_event_id)}
            for u in users
        ],
        "resources": [
            {"id": r.id, "name": r.name, "busy": resource_periods(r, start, end, exclude_event_id)} for r in resources
        ],
    }
