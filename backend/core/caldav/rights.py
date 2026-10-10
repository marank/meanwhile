"""
Radicale rights plugin backed by Django calendar memberships.
"""

from django.db import connection
from radicale import rights as base_rights

from core.models import Calendar, User
from core.models.base import Role
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

            owner_email, calendar_id = parts[0], parts[1]
            owner = User.objects.filter(email__iexact=owner_email).first()
            if owner is None:
                return ""

            calendar = Calendar.objects.filter(id=calendar_id, owner=owner).first()
            if calendar is None:
                return ""
            # Same rules as the API: direct, group or public membership; non-members get nothing.
            membership = get_membership(calendar, user_obj)
            if membership is None:
                return ""
            if membership.role == Role.VIEWER:
                return "Rr"
            return "RWrw"
        finally:
            connection.close()
