"""
Custom django-allauth account adapter.
"""

from django.conf import settings as django_settings

from allauth.account.adapter import DefaultAccountAdapter

from core.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request) -> bool:
        return getattr(django_settings, "ALLOW_REGISTRATION", True)

    def save_user(self, request, user, form, commit=True):
        # Let allauth + our SignupForm set email, password, display_name.
        user = super().save_user(request, user, form, commit=False)

        # Ensure display_name from the extra signup form is present.
        if hasattr(form, "cleaned_data"):
            user.display_name = form.cleaned_data.get("display_name") or user.display_name

        # Grant admin rights to the very first user or a configured admin email.
        email = (user.email or "").lower()
        is_first = not User.objects.exists()
        admin_email = (getattr(django_settings, "ADMIN_EMAIL", "") or "").lower()
        if is_first or (admin_email and email == admin_email):
            user.is_admin = True
            user.is_staff = True
            user.is_superuser = True

        if commit:
            user.save()
        return user
