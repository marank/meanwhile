"""
Radicale rights plugin backed by Django calendar memberships.
"""

from django.db import connection
from radicale import rights as base_rights

from core.models import Calendar, User
from core.models.base import Role
from core.caldav.storage import calendar_by_dav_name
from core.services.permissions import get_membership


class Rights(base_rights.BaseRights):
    def authorization(self, user: str, path: str) -> str:
        if not user:
            return ""

        parts = [p for p in path.split("/") if p]
        if not parts:
            return "RWrw"

        try:
            user_obj = User.objects.filter(email__iexact=user).first()
            if user_obj is None:
                return ""

            if len(parts) == 1:
                if parts[0].lower() == user.lower():
                    return "RWrw"
                return ""

            home_email, name = parts[0], parts[1]
            calendar = calendar_by_dav_name(Calendar.objects.select_related("owner"), name)
            if calendar is None:
                # A new calendar may be created in the user's own home (lowercase: calendars only, no folders).
                if len(parts) == 2 and home_email.lower() == user.lower():
                    return "rw"
                return ""
            # A calendar is reached through the user's own calendar home or through its owner's.
            if home_email.lower() not in (user.lower(), calendar.owner.email.lower()):
                return ""
            # Same rules as the API: direct, group or public membership; non-members get nothing.
            membership = get_membership(calendar, user_obj)
            if membership is None:
                return ""
            if membership.role == Role.READ:
                return "Rr"
            return "RWrw"
        finally:
            connection.close()
