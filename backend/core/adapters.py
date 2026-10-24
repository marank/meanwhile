"""
Custom django-allauth account adapter.
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings as django_settings


class AccountAdapter(DefaultAccountAdapter):
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
