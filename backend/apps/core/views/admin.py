"""
Admin endpoints for users and global settings.
"""

from typing import Any

from django.db.models import Prefetch
from ninja import Router

from apps.core.models import AppSettings, User, UserGroup, get_or_create_app_settings
from apps.core.schemas import (
    AdminPasswordResetOut,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AppSettingsOut,
    AppSettingsUpdate,
    GroupOut,
    OkOut,
)
from apps.core.services import accounts, users
from apps.core.views.common import AuthedRequest, require_admin

router = Router()


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "has_password": user.has_usable_password(),
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
    all_users = User.objects.prefetch_related(Prefetch("groups", queryset=UserGroup.objects.all())).order_by("email")
    return [_serialize_user(u) for u in all_users]


@router.post("/admin/users", response=AdminUserOut)
def admin_create_user(request: AuthedRequest, payload: AdminUserCreate) -> dict[str, Any]:
    require_admin(request)
    return _serialize_user(users.create_user(payload))


@router.get("/admin/users/{user_id}", response=AdminUserOut)
def admin_get_user(request: AuthedRequest, user_id: str) -> dict[str, Any]:
    require_admin(request)
    user = User.objects.prefetch_related("groups").get(id=user_id)
    return _serialize_user(user)


@router.patch("/admin/users/{user_id}", response=AdminUserOut)
def admin_update_user(request: AuthedRequest, user_id: str, payload: AdminUserUpdate) -> dict[str, Any]:
    require_admin(request)
    return _serialize_user(users.update_user(request.user, user_id, payload.dict(exclude_unset=True)))


@router.delete("/admin/users/{user_id}", response=OkOut)
def admin_delete_user(request: AuthedRequest, user_id: str) -> dict[str, bool]:
    require_admin(request)
    users.delete_user(request.user, user_id)
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/reset-password",
    response=AdminPasswordResetOut,
)
def admin_reset_password(request: AuthedRequest, user_id: str) -> dict[str, str]:
    require_admin(request)
    return {"password": users.reset_password(request.user, user_id)}


@router.post("/admin/users/{user_id}/invite", response=OkOut)
def admin_invite_user(request: AuthedRequest, user_id: str) -> dict[str, bool]:
    """Emails the user about their account; without a password, with the link to choose one."""
    require_admin(request)
    accounts.send_invitation(users.user_to_change(request.user, user_id), request.user)
    return {"ok": True}
