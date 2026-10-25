"""
Calendar category endpoints.
"""

from django.db.models import QuerySet
from ninja import Router

from core.models import Category
from core.models.base import Role
from core.schemas import CategoryCreate, CategoryOut, CategoryUpdate, OkOut
from core.services.permissions import get_member_calendar
from core.views.common import AuthedRequest

router = Router()


@router.get("/calendars/{calendar_id}/categories", response=list[CategoryOut])
def list_categories(request: AuthedRequest, calendar_id: str) -> QuerySet[Category]:
    calendar, _ = get_member_calendar(calendar_id, request.user)
    return Category.objects.filter(calendar=calendar).order_by("name")


@router.post("/calendars/{calendar_id}/categories", response=CategoryOut)
def create_category(request: AuthedRequest, calendar_id: str, payload: CategoryCreate) -> Category:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    return Category.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )


@router.patch("/calendars/{calendar_id}/categories/{category_id}", response=CategoryOut)
def update_category(request: AuthedRequest, calendar_id: str, category_id: str, payload: CategoryUpdate) -> Category:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    category = Category.objects.get(id=category_id, calendar=calendar)
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(category, attr, value)
    category.save()
    return category


@router.delete("/calendars/{calendar_id}/categories/{category_id}", response=OkOut)
def delete_category(request: AuthedRequest, calendar_id: str, category_id: str) -> dict[str, bool]:
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    Category.objects.filter(id=category_id, calendar=calendar).delete()
    return {"ok": True}
