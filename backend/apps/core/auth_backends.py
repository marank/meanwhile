"""
Authentication backends (settings.AUTHENTICATION_BACKENDS).
"""

from typing import Any

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import QuerySet


class AppModelBackend(ModelBackend):
    """Django's model backend for an app whose groups aren't Django's: `User.groups` holds the groups calendars
    are shared with (UserGroup), which carry no Django permissions. The model backend would look for them
    among auth.Group and fail (e.g. on the admin's login page for users who aren't superusers)."""

    def _get_group_permissions(self, user_obj: Any) -> QuerySet[Permission]:
        return Permission.objects.none()
