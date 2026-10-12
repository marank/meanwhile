"""
Global search endpoint.
"""

from ninja import Router
from ninja.errors import HttpError

from core.schemas import SearchResult
from core.services.permissions import get_member_calendar
from core.services.search import (
    search_calendar_members,
    search_categories,
    search_groups,
    search_resources,
    search_users,
)

router = Router()


@router.get("/search", response=list[SearchResult])
def search(
    request,
    entity: str,
    q: str = "",
    limit: int = 20,
    calendar_id: str | None = None,
):
    if entity == "users":
        return search_users(q, limit)
    if entity == "groups":
        return search_groups(q, limit)
    if entity in {"resources", "locations", "categories", "members"}:
        if calendar_id is None:
            raise HttpError(422, "calendar_id is required for this entity")
        get_member_calendar(calendar_id, request.user)
        if entity in {"resources", "locations"}:
            # "locations": the resources offered in an event's location field; "resources" the others.
            return search_resources(calendar_id, q, limit, locations=entity == "locations")
        if entity == "members":
            return search_calendar_members(calendar_id, q, limit)
        return search_categories(calendar_id, q, limit)
    raise HttpError(400, "Unknown search entity")
