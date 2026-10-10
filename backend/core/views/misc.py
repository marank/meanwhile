"""
Health and public settings endpoints.
"""

from ninja import Router

from core.api import CSRFRouter
from core.models import get_or_create_app_settings
from core.schemas import AppSettingsOut

router = CSRFRouter()


@router.get("/health")
def health(request):
    return {"status": "ok"}


@router.get("/settings", response=AppSettingsOut)
def public_settings(request):
    return get_or_create_app_settings()
