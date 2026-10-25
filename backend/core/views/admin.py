"""
Admin endpoints for users and global settings.
"""

import secrets
from typing import Any

from django.db.models import Prefetch
from ninja import Router
from ninja.errors import HttpError

from core.models import AppSettings, User, UserGroup, get_or_create_app_settings
from core.schemas import (
    AdminPasswordResetOut,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AppSettingsOut,
    AppSettingsUpdate,
    GroupOut,
    OkOut,
)
from core.views.common import AuthedRequest, require_admin

router = Router()


def _require_may_change(request: AuthedRequest, user: User) -> None:
    """App admins aren't superusers (Django admin, every table): only superusers change those,
    so an app admin can't take one over by its email or password."""
    if user.is_superuser and not request.user.is_superuser:
        raise HttpError(403, "Only superusers can change superusers")


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "groups": [GroupOut.model_validate(g) for g in user.groups.all()],
    }


@router.get("/admin/settings", response=AppSettingsOut)
def admin_settings(request: AuthedRequest) -> AppSettings:
    require_admin(request)
    return get_or_create_app_settings()


@router.patch("/admin/settings", response=AppSettingsOut)
def admin_settings_update(request: AuthedRequest, payload: AppSettingsUpdate) -> AppSettings:
    require_admin(request)
    settings_obj = get_or_create_app_settings()
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(settings_obj, attr, value)
    settings_obj.save()
    return settings_obj


@router.get("/admin/users", response=list[AdminUserOut])
def admin_users(request: AuthedRequest) -> list[dict[str, Any]]:
    require_admin(request)
    users = User.objects.prefetch_related(Prefetch("groups", queryset=UserGroup.objects.all())).order_by("email")
    return [_serialize_user(u) for u in users]


@router.post("/admin/users", response=AdminUserOut)
def admin_create_user(request: AuthedRequest, payload: AdminUserCreate) -> dict[str, Any]:
    require_admin(request)
    if User.objects.filter(email__iexact=payload.email).exists():
        raise HttpError(400, "A user with this email already exists")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        is_admin=payload.is_admin,
        is_active=payload.is_active,
    )
    user.set_password(payload.password)
    user.save()
    if payload.group_ids:
        user.groups.set(UserGroup.objects.filter(id__in=payload.group_ids))
    return _serialize_user(user)


@router.get("/admin/users/{user_id}", response=AdminUserOut)
def admin_get_user(request: AuthedRequest, user_id: str) -> dict[str, Any]:
    require_admin(request)
    user = User.objects.prefetch_related("groups").get(id=user_id)
    return _serialize_user(user)


@router.patch("/admin/users/{user_id}", response=AdminUserOut)
def admin_update_user(request: AuthedRequest, user_id: str, payload: AdminUserUpdate) -> dict[str, Any]:
    require_admin(request)
    user = User.objects.prefetch_related("groups").get(id=user_id)
    _require_may_change(request, user)
    data = payload.dict(exclude_unset=True)

    is_self = user.id == request.user.id
    protected = {"is_admin", "is_active"}
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


@router.delete("/admin/users/{user_id}", response=OkOut)
def admin_delete_user(request: AuthedRequest, user_id: str) -> dict[str, bool]:
    require_admin(request)
    if str(request.user.id) == user_id:
        raise HttpError(403, "Cannot delete yourself")
    user = User.objects.filter(id=user_id).first()
    if user is not None:
        _require_may_change(request, user)
        user.delete()
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/reset-password",
    response=AdminPasswordResetOut,
)
def admin_reset_password(request: AuthedRequest, user_id: str) -> dict[str, str]:
    require_admin(request)
    user = User.objects.get(id=user_id)
    _require_may_change(request, user)
    new_password = secrets.token_urlsafe(16)
    user.set_password(new_password)
    user.save()
    return {"password": new_password}
