"""
Admin endpoints for users and global settings.
"""

import secrets

from django.db.models import Prefetch
from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import User, UserGroup, get_or_create_app_settings
from core.schemas import (
    AdminPasswordResetOut,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AppSettingsOut,
    AppSettingsUpdate,
    GroupOut,
)
from core.views.common import require_admin

router = CSRFRouter()


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "groups": [GroupOut.model_validate(g) for g in user.groups.all()],
    }


@router.get("/admin/settings", response=AppSettingsOut, auth=django_auth)
def admin_settings(request):
    require_admin(request)
    return get_or_create_app_settings()


@router.patch("/admin/settings", response=AppSettingsOut, auth=django_auth)
def admin_settings_update(request, payload: AppSettingsUpdate):
    require_admin(request)
    settings_obj = get_or_create_app_settings()
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(settings_obj, attr, value)
    settings_obj.save()
    return settings_obj


@router.get("/admin/users", response=list[AdminUserOut], auth=django_auth)
def admin_users(request):
    require_admin(request)
    users = User.objects.prefetch_related(Prefetch("groups", queryset=UserGroup.objects.all())).order_by("email")
    return [_serialize_user(u) for u in users]


@router.post("/admin/users", response=AdminUserOut, auth=django_auth)
def admin_create_user(request, payload: AdminUserCreate):
    require_admin(request)
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        is_admin=payload.is_admin,
        is_staff=payload.is_staff,
        is_superuser=payload.is_superuser,
        is_active=payload.is_active,
    )
    user.set_password(payload.password)
    user.save()
    if payload.group_ids:
        user.groups.set(UserGroup.objects.filter(id__in=payload.group_ids))
    return _serialize_user(user)


@router.get("/admin/users/{user_id}", response=AdminUserOut, auth=django_auth)
def admin_get_user(request, user_id: str):
    require_admin(request)
    user = User.objects.prefetch_related("groups").get(id=user_id)
    return _serialize_user(user)


@router.patch("/admin/users/{user_id}", response=AdminUserOut, auth=django_auth)
def admin_update_user(request, user_id: str, payload: AdminUserUpdate):
    require_admin(request)
    user = User.objects.prefetch_related("groups").get(id=user_id)
    data = payload.dict(exclude_unset=True)

    is_self = str(user.id) == str(request.user.id)
    protected = {"is_admin", "is_staff", "is_superuser", "is_active"}
    if is_self:
        for flag in protected:
            if data.get(flag) is False:
                raise HttpError(403, f"Cannot remove your own {flag}")

    group_ids = data.pop("group_ids", None)
    for attr, value in data.items():
        if attr == "password":
            user.set_password(value)
        else:
            setattr(user, attr, value)
    user.save()
    if group_ids is not None:
        user.groups.set(UserGroup.objects.filter(id__in=group_ids))
    return _serialize_user(user)


@router.delete("/admin/users/{user_id}", auth=django_auth)
def admin_delete_user(request, user_id: str):
    require_admin(request)
    if str(request.user.id) == user_id:
        raise HttpError(403, "Cannot delete yourself")
    User.objects.filter(id=user_id).delete()
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/reset-password",
    response=AdminPasswordResetOut,
    auth=django_auth,
)
def admin_reset_password(request, user_id: str):
    require_admin(request)
    user = User.objects.get(id=user_id)
    new_password = secrets.token_urlsafe(16)
    user.set_password(new_password)
    user.save()
    return {"password": new_password}
