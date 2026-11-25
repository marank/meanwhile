"""
Changing accounts: the admin's user management and the user's own profile.
"""

import secrets
from typing import Any

from django.utils.translation import gettext, gettext_noop
from ninja.errors import HttpError

from apps.core.models import User, UserGroup
from apps.core.schemas import AdminUserCreate
from apps.core.services.notifications import email_preferences
from apps.core.services.reminders import reminders_changed


def user_to_change(actor: User, user_id: str) -> User:
    """The user an admin is about to change. App admins aren't superusers (Django admin, every table):
    only superusers change those, so an app admin can't take one over by its email or password."""
    user = User.objects.prefetch_related("groups").get(id=user_id)
    if user.is_superuser and not actor.is_superuser:
        raise HttpError(403, gettext("Only superusers can change superusers"))
    return user


def create_user(data: AdminUserCreate) -> User:
    if User.objects.filter(email__iexact=data.email).exists():
        raise HttpError(400, gettext("A user with this email already exists"))
    user = User(
        email=data.email,
        display_name=data.display_name,
        is_admin=data.is_admin,
        is_active=data.is_active,
    )
    if data.password:
        user.set_password(data.password)
    else:
        user.set_unusable_password()
    user.save()
    if data.group_ids:
        user.groups.set(UserGroup.objects.filter(id__in=data.group_ids))
    return user


# The rights admins can't take from themselves, and what they are told when they try.
OWN_FLAG_MESSAGES = {
    "is_admin": gettext_noop("You cannot take away your own admin rights"),
    "is_active": gettext_noop("You cannot deactivate yourself"),
}


def update_user(actor: User, user_id: str, data: dict[str, Any]) -> User:
    """Changes what `data` names (the PATCH's set fields); admins can't take their own rights away."""
    user = user_to_change(actor, user_id)
    if user.id == actor.id:
        for flag, message in OWN_FLAG_MESSAGES.items():
            if data.get(flag) is False:
                raise HttpError(403, gettext(message))
    group_ids = data.pop("group_ids", None)
    for attr, value in data.items():
        if attr == "password":
            user.set_password(value)
        else:
            setattr(user, attr, value)
    user.save()
    if group_ids is not None:
        user.groups.set(UserGroup.objects.filter(id__in=group_ids))
    return user


def delete_user(actor: User, user_id: str) -> None:
    if str(actor.id) == user_id:
        raise HttpError(403, gettext("Cannot delete yourself"))
    if User.objects.filter(id=user_id).exists():
        user_to_change(actor, user_id).delete()


def reset_password(actor: User, user_id: str) -> str:
    """Gives the user a new random password, which the admin passes on."""
    user = user_to_change(actor, user_id)
    new_password = secrets.token_urlsafe(16)
    user.set_password(new_password)
    user.save()
    return new_password


def update_profile(user: User, data: dict[str, Any]) -> User:
    """Changes the user's own settings; email choices left out (or null) stay as they are."""
    choices = data.pop("email_notifications", None)
    if data.get("timezone", user.timezone) != user.timezone:
        # All-day occurrences begin at midnight where the user is.
        reminders_changed(user_id=user.id)
    for attr, value in data.items():
        setattr(user, attr, value)
    if choices:
        user.email_notifications = {
            **email_preferences(user),
            **{kind: value for kind, value in choices.items() if value is not None},
        }
    user.save()
    return user
