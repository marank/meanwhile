"""
Calendar category endpoints.
"""

from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import Calendar, Category
from core.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from core.services.permissions import get_membership, has_at_least_role
from core.models.base import Role

router = CSRFRouter()


def _require_editor(user, calendar: Calendar):
    membership = get_membership(calendar, user)
    if membership is None or not has_at_least_role(membership, Role.EDITOR):
        raise HttpError(403, "Editor access required")


@router.get("/calendars/{calendar_id}/categories", response=list[CategoryOut], auth=django_auth)
def list_categories(request, calendar_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    if get_membership(calendar, request.user) is None and not calendar.is_public:
        raise HttpError(403, "Not a member of this calendar")
    return Category.objects.filter(calendar=calendar).order_by("name")


@router.post("/calendars/{calendar_id}/categories", response=CategoryOut, auth=django_auth)
def create_category(request, calendar_id: str, payload: CategoryCreate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    return Category.objects.create(
        calendar=calendar,
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )


@router.patch("/calendars/{calendar_id}/categories/{category_id}", response=CategoryOut, auth=django_auth)
def update_category(request, calendar_id: str, category_id: str, payload: CategoryUpdate):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    category = Category.objects.get(id=category_id, calendar=calendar)
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(category, attr, value)
    category.save()
    return category


@router.delete("/calendars/{calendar_id}/categories/{category_id}", auth=django_auth)
def delete_category(request, calendar_id: str, category_id: str):
    calendar = Calendar.objects.get(id=calendar_id)
    _require_editor(request.user, calendar)
    Category.objects.filter(id=category_id, calendar=calendar).delete()
    return {"ok": True}
