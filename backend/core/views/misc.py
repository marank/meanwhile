"""
Health and public settings endpoints.
"""

from django.http import HttpRequest
from ninja import Router

from core.models import AppSettings, get_or_create_app_settings
from core.schemas import AppSettingsOut

router = Router()


@router.get("/health", auth=None)
def health(request: HttpRequest) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/settings", response=AppSettingsOut, auth=None)
def public_settings(request: HttpRequest) -> AppSettings:
    return get_or_create_app_settings()
