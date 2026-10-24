"""
Radicale rights plugin backed by Django calendar memberships.
"""

from radicale import rights as base_rights

from core.caldav.request import once_per_request
from core.caldav.storage import calendar_in_home, user_by_email
from core.models import Calendar
from core.models.base import Role
from core.services.permissions import get_membership


class Rights(base_rights.BaseRights):
    def authorization(self, user: str, path: str) -> str:
        if not user:
            return ""

        parts = [p for p in path.split("/") if p]
        if not parts:
            return "RWrw"
        # Radicale asks for every item it lists; the rights of an item are those of its calendar.
        home, calendar = parts[0].lower(), parts[1] if len(parts) > 1 else None
        key = ("rights", user.lower(), home, calendar, len(parts) > 2)
        return once_per_request(key, lambda: self._authorization(user, parts))

    def _authorization(self, user: str, parts: list[str]) -> str:
        user_obj = user_by_email(user)
        if user_obj is None:
            return ""

        if len(parts) == 1:
            if parts[0].lower() == user.lower():
                return "RWrw"
            return ""

        home_email, name = parts[0], parts[1]
        home = user_by_email(home_email)
        calendar = calendar_in_home(home, name, Calendar.objects.select_related("owner")) if home else None
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
