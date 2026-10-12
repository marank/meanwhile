"""
Global search across users, groups, resources and categories.
"""

from django.db.models import Q

from core.models.resources import Category, Resource
from core.models.users import User, UserGroup


MAX_LIMIT = 20


def search_users(q: str, limit: int = MAX_LIMIT):
    q = q.strip()
    if len(q) < 2:
        return []
    users = (
        User.objects.filter(
            Q(email__icontains=q) | Q(display_name__icontains=q)
        )
        .order_by("display_name", "email")
        .values("id", "display_name", "email")[:limit]
    )
    return [
        {"id": u["id"], "type": "user", "label": u["display_name"], "subtitle": u["email"]}
        for u in users
    ]


def search_calendar_members(calendar_id: str, q: str, limit: int = MAX_LIMIT):
    q = q.strip()
    users = User.objects.filter(memberships__calendar_id=calendar_id)
    if q:
        users = users.filter(Q(email__icontains=q) | Q(display_name__icontains=q))
    users = users.order_by("display_name", "email").values("id", "display_name", "email")[:limit]
    return [
        {"id": u["id"], "type": "user", "label": u["display_name"], "subtitle": u["email"]}
        for u in users
    ]


def search_groups(q: str, limit: int = MAX_LIMIT):
    query = UserGroup.objects.all()
    if q.strip():
        query = query.filter(name__icontains=q.strip())
    groups = query.order_by("name").values("id", "name", "description")[:limit]
    return [
        {
            "id": g["id"],
            "type": "group",
            "label": g["name"],
            "subtitle": g["description"],
        }
        for g in groups
    ]


def search_resources(calendar_id: str, q: str, limit: int = MAX_LIMIT, locations: bool = False):
    """Bookable resources: places for an event's location field, or the others for its resource field."""
    # Only offer resources that can be booked: active and not archived (deleted).
    query = Resource.objects.filter(
        calendar_id=calendar_id, is_active=True, archived_at__isnull=True, is_location=locations
    )
    if q.strip():
        query = query.filter(name__icontains=q.strip())
    resources = query.order_by("name").values(
        "id", "name", "description", "requires_approval", "color", "icon", "is_location"
    )[:limit]
    return [
        {
            "id": r["id"],
            "type": "resource",
            "label": r["name"],
            "subtitle": r["description"],
            "meta": {
                "requires_approval": r["requires_approval"],
                "color": r["color"],
                "icon": r["icon"],
                "is_location": r["is_location"],
            },
        }
        for r in resources
    ]


def search_categories(calendar_id: str, q: str, limit: int = MAX_LIMIT):
    query = Category.objects.filter(calendar_id=calendar_id)
    if q.strip():
        query = query.filter(name__icontains=q.strip())
    categories = query.order_by("name").values("id", "name", "color")[:limit]
    return [
        {
            "id": c["id"],
            "type": "category",
            "label": c["name"],
            "meta": {"color": c["color"]},
        }
        for c in categories
    ]
