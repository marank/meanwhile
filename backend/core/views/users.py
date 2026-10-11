"""
User profile and app-password endpoints.
"""

import secrets

from django.contrib.auth.hashers import make_password
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import AppPassword, OverviewSettings, User, get_or_create_app_settings
from core.models.calendar_colors import APP_COLORS
from core.schemas import (
    AppPasswordCreated,
    AppPasswordCreate,
    AppPasswordOut,
    OverviewSettingsOut,
    OverviewSettingsUpdate,
    UserOut,
    UserUpdate,
)

router = CSRFRouter()


@router.get("/users/me", response=UserOut, auth=django_auth)
def me(request):
    return request.user


@router.patch("/users/me", response=UserOut, auth=django_auth)
def update_me(request, payload: UserUpdate):
    user: User = request.user
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(user, attr, value)
    user.save()
    return user


def _overview_settings(user: User) -> OverviewSettings:
    """The user's overview settings; created on first use from the app defaults and the app color preset."""
    try:
        return user.overview_settings
    except OverviewSettings.DoesNotExist:
        app_settings = get_or_create_app_settings()
        return OverviewSettings.objects.create(
            user=user,
            first_weekday=app_settings.default_first_weekday,
            show_weekends=app_settings.default_show_weekends,
            weekend_days=app_settings.default_weekend_days,
            show_week_numbers=app_settings.default_show_week_numbers,
            **APP_COLORS,
        )


@router.get("/users/me/overview", response=OverviewSettingsOut, auth=django_auth)
def get_overview_settings(request):
    return _overview_settings(request.user)


@router.patch("/users/me/overview", response=OverviewSettingsOut, auth=django_auth)
def update_overview_settings(request, payload: OverviewSettingsUpdate):
    settings = _overview_settings(request.user)
    data = payload.dict(exclude_unset=True)
    if "weekend_days" in data:
        data["weekend_days"] = sorted(set(data["weekend_days"]))
    for attr, value in data.items():
        setattr(settings, attr, value)
    settings.save()
    return settings


@router.get("/users/me/app-passwords", response=list[AppPasswordOut], auth=django_auth)
def list_app_passwords(request):
    return request.user.app_passwords.all().order_by("-created_at")


@router.post("/users/me/app-passwords", response=AppPasswordCreated, auth=django_auth)
def create_app_password(request, payload: AppPasswordCreate):
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


@router.delete("/users/me/app-passwords/{password_id}", auth=django_auth)
def delete_app_password(request, password_id: str):
    request.user.app_passwords.filter(id=password_id).delete()
    return {"ok": True}
