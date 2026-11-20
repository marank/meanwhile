"""
Custom django-allauth account adapter.
"""

from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from allauth.account.adapter import DefaultAccountAdapter
from django import forms
from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.utils import translation

from apps.core.models import User
from apps.core.services import accounts, mail
from apps.core.services.mail import app_name, language_of


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]  # allauth ships no types
    def format_email_subject(self, subject: str) -> str:
        # The app's name, not the Django site's ("example.com"), as in the app's own emails.
        return f"[{app_name()}] {subject}"

    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        # allauth's emails (e.g. the password reset code) greet from the Django site ("example.com");
        # they come from the app instead, in the language of the account they're for.
        name = app_name()
        site = SimpleNamespace(name=name, domain=urlparse(django_settings.APP_URL).netloc or name)
        context = {**context, "current_site": site}
        user = User.objects.filter(email__iexact=email).first()
        with translation.override(language_of(user)):
            message = self.render_mail(template_prefix, email, context)
        if not isinstance(message, EmailMultiAlternatives):  # allauth's plain-text emails
            message = EmailMultiAlternatives(
                message.subject, message.body, message.from_email, message.to, reply_to=message.reply_to
            )
        # As a job, like the app's own emails: not inside the request, and retried while the server fails.
        mail.send([message])

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
