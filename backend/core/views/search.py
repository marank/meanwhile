"""
Global search endpoint.
"""

from typing import Any, Literal

from ninja import Router
from ninja.errors import HttpError

from core.schemas import SearchResult
from core.services.permissions import get_member_calendar
from core.services.search import (
    MAX_LIMIT,
    search_calendar_members,
    search_categories,
    search_groups,
    search_resources,
    search_users,
)
from core.views.common import AuthedRequest

router = Router()

SearchEntity = Literal["users", "members", "groups", "resources", "locations", "categories"]


@router.get("/search", response=list[SearchResult])
def search(
    request: AuthedRequest,
    entity: SearchEntity,
    q: str = "",
    limit: int = 20,
    calendar_id: str | None = None,
) -> list[dict[str, Any]]:
    # No more than a dropdown shows: listing every user with their email is not what search is for.
    limit = max(1, min(limit, MAX_LIMIT))
    if entity == "users":
        return search_users(q, limit)
    if entity == "groups":
        return search_groups(q, limit)
    # The others search within a calendar.
    if calendar_id is None:
        raise HttpError(422, "calendar_id is required for this entity")
    get_member_calendar(calendar_id, request.user)
    if entity in {"resources", "locations"}:
        # "locations": the resources offered in an event's location field; "resources" the others.
        return search_resources(calendar_id, q, limit, locations=entity == "locations")
    if entity == "members":
        return search_calendar_members(calendar_id, q, limit)
    return search_categories(calendar_id, q, limit)
