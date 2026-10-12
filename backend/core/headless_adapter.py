"""
Custom django-allauth headless adapter.

Returns user payloads that match the app's existing UserOut schema so the SPA
can consume them directly.
"""

from allauth.headless.adapter import DefaultHeadlessAdapter

from core.services.notifications import email_preferences


class HeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
            "time_format": user.time_format,
            "date_format": user.date_format,
            "timezone": user.timezone,
            "language": user.language,
            "email_notifications": email_preferences(user),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
