"""
Custom django-allauth account adapter.
"""

from types import SimpleNamespace
from urllib.parse import urlparse

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings as django_settings
from django.utils import translation

from core.models import User
from core.services.mail import app_name, language_of


class AccountAdapter(DefaultAccountAdapter):
    def format_email_subject(self, subject) -> str:
        # The app's name, not the Django site's ("example.com"), as in the app's own emails.
        return f"[{app_name()}] {subject}"

    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        # allauth's emails (e.g. the password reset code) greet from the Django site ("example.com");
        # they come from the app instead, in the language of the account they're for.
        name = app_name()
        site = SimpleNamespace(name=name, domain=urlparse(django_settings.APP_URL).netloc or name)
        context = {**context, "current_site": site}
        user = User.objects.filter(email__iexact=email).first()
        with translation.override(language_of(user)):
            super().send_mail(template_prefix, email, context)

    def is_open_for_signup(self, request) -> bool:
        return getattr(django_settings, "ALLOW_REGISTRATION", True)

    def save_user(self, request, user, form, commit=True):
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
