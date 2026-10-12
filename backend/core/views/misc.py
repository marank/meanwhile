"""
Health and public settings endpoints.
"""


from ninja import Router

from core.models import get_or_create_app_settings
from core.schemas import AppSettingsOut

router = Router()


@router.get("/health", auth=None)
def health(request):
    return {"status": "ok"}


@router.get("/settings", response=AppSettingsOut, auth=None)
def public_settings(request):
    return get_or_create_app_settings()
