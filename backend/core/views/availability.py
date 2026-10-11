"""
Availability endpoint: when people and resources are taken, for planning an event.
"""

from datetime import datetime, timedelta

from ninja import Query
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Resource, User
from core.schemas import AvailabilityOut
from core.services.availability import resource_periods, user_periods
from core.services.permissions import get_membership
from core.services.recurrence import make_aware

router = CSRFRouter()

MAX_RANGE = timedelta(days=62)


@router.get("/availability", response=AvailabilityOut, auth=django_auth)
def availability(
    request,
    start: datetime,
    end: datetime,
    user_ids: list[str] = Query([]),
    resource_ids: list[str] = Query([]),
    exclude_event_id: str | None = None,
):
    """Busy periods only, no titles or details. Users can be looked up by anyone signed in, as in
    the user search; resources only by members of their calendar."""
    start, end = make_aware(start), make_aware(end)
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
            {"id": r.id, "name": r.name, "busy": resource_periods(r, start, end, exclude_event_id)}
            for r in resources
        ],
    }
