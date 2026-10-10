"""
User profile and app-password endpoints.
"""

import secrets

from django.contrib.auth.hashers import make_password
from ninja import Router
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import AppPassword, User
from core.schemas import (
    AppPasswordCreated,
    AppPasswordCreate,
    AppPasswordOut,
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
