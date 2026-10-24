"""
Calendar category endpoints.
"""

from ninja import Router

from core.models import Category
from core.models.base import Role
from core.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from core.services.permissions import get_member_calendar

router = Router()


@router.get("/calendars/{calendar_id}/categories", response=list[CategoryOut])
def list_categories(request, calendar_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user)
    return Category.objects.filter(calendar=calendar).order_by("name")


@router.post("/calendars/{calendar_id}/categories", response=CategoryOut)
def create_category(request, calendar_id: str, payload: CategoryCreate):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    return Category.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )


@router.patch("/calendars/{calendar_id}/categories/{category_id}", response=CategoryOut)
def update_category(request, calendar_id: str, category_id: str, payload: CategoryUpdate):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    category = Category.objects.get(id=category_id, calendar=calendar)
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(category, attr, value)
    category.save()
    return category


@router.delete("/calendars/{calendar_id}/categories/{category_id}")
def delete_category(request, calendar_id: str, category_id: str):
    calendar, _ = get_member_calendar(calendar_id, request.user, Role.FULL, "Full access required")
    Category.objects.filter(id=category_id, calendar=calendar).delete()
    return {"ok": True}
