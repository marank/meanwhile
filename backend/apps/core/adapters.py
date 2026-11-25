"""
Custom django-allauth account adapter.
"""

import logging
from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django import forms
from django.conf import settings as django_settings
from django.http import HttpRequest

from apps.core.models import User
from apps.core.services import accounts

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]  # allauth ships no types
    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        # allauth's own emails are plain text in its own wording, unlike the app's. The settings keep
        # it from sending any (no email verification, login codes, notifications or mails to unknown
        # addresses); the password reset link goes out as the app's own email below. Should a setting
        # change make allauth send one after all, it is dropped rather than sent in allauth's look.
        logger.warning("Not sending allauth's own email %s", template_prefix)

    def send_password_reset_mail(self, user: User, email: str, context: dict[str, Any]) -> None:
        # Laid out like the app's other emails, not as allauth's plain text.
        accounts.send_password_reset(user, context["password_reset_url"])

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return bool(getattr(django_settings, "ALLOW_REGISTRATION", True))

    def save_user(self, request: HttpRequest, user: User, form: forms.Form, commit: bool = True) -> User:
        # Let allauth + our SignupForm set email, password, display_name.
        user = super().save_user(request, user, form, commit=False)

        # Ensure display_name from the extra signup form is present.
        if hasattr(form, "cleaned_data"):
            user.display_name = form.cleaned_data.get("display_name") or user.display_name

        # Signing up never makes anyone admin, the first user or one of ADMIN_EMAIL included: emails
        # aren't verified, so whoever comes first would be. `manage.py ensure_admin` sets up the admin.

        if commit:
            user.save()
        return user
