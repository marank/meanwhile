"""
User profile and app-password endpoints.
"""

import secrets
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db.models import QuerySet
from ninja import Router

from core.models import AppPassword, OverviewSettings, User
from core.models.calendar_colors import APP_COLORS
from core.schemas import (
    AppPasswordCreate,
    AppPasswordCreated,
    AppPasswordOut,
    OkOut,
    OverviewSettingsOut,
    OverviewSettingsUpdate,
    ProfileOut,
    UserUpdate,
)
from core.services.notifications import email_preferences
from core.services.reminders import reminders_changed
from core.views.common import AuthedRequest

router = Router()


@router.get("/users/me", response=ProfileOut)
def me(request: AuthedRequest) -> User:
    return request.user


@router.patch("/users/me", response=ProfileOut)
def update_me(request: AuthedRequest, payload: UserUpdate) -> User:
    user: User = request.user
    data = payload.dict(exclude_unset=True)
    choices = data.pop("email_notifications", None)
    if data.get("timezone", user.timezone) != user.timezone:
        # All-day occurrences begin at midnight where the user is.
        reminders_changed(user_id=user.id)
    for attr, value in data.items():
        setattr(user, attr, value)
    if choices:
        user.email_notifications = {
            **email_preferences(user),
            **{kind: value for kind, value in choices.items() if value is not None},
        }
    user.save()
    return user


def _overview_settings(user: User) -> OverviewSettings:
    """The user's overview settings. Until they first save some, unsaved ones with the app color
    preset; the week layout stays empty until the user sets it, following the app defaults."""
    try:
        return user.overview_settings
    except OverviewSettings.DoesNotExist:
        return OverviewSettings(user=user, **APP_COLORS)


@router.get("/users/me/settings", response=OverviewSettingsOut)
def get_overview_settings(request: AuthedRequest) -> OverviewSettings:
    return _overview_settings(request.user)


@router.patch("/users/me/settings", response=OverviewSettingsOut)
def update_overview_settings(request: AuthedRequest, payload: OverviewSettingsUpdate) -> OverviewSettings:
    settings = _overview_settings(request.user)
    data = payload.dict(exclude_unset=True)
    if data.get("weekend_days") is not None:
        data["weekend_days"] = sorted(set(data["weekend_days"]))
    for attr, value in data.items():
        # null puts a layout value back to following the app default; the other fields need one.
        if value is not None or attr in OverviewSettings.LAYOUT_FIELDS:
            setattr(settings, attr, value)
    settings.save()
    return settings


@router.get("/users/me/app-passwords", response=list[AppPasswordOut])
def list_app_passwords(request: AuthedRequest) -> QuerySet[AppPassword]:
    return request.user.app_passwords.all().order_by("-created_at")


@router.post("/users/me/app-passwords", response=AppPasswordCreated)
def create_app_password(request: AuthedRequest, payload: AppPasswordCreate) -> dict[str, Any]:
    user: User = request.user
    plaintext = secrets.token_urlsafe(32)
    entry = AppPassword.objects.create(
        user=user,
        label=payload.label,
        password_hash=make_password(plaintext),
    )
    return {
        "id": entry.id,
        "label": entry.label,
        "password": plaintext,
    }


@router.delete("/users/me/app-passwords/{password_id}", response=OkOut)
def delete_app_password(request: AuthedRequest, password_id: str) -> dict[str, bool]:
    request.user.app_passwords.filter(id=password_id).delete()
    return {"ok": True}
