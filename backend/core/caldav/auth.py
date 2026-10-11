"""
Radicale auth plugin backed by Django users and app passwords.
"""

from datetime import datetime, timezone

from django.contrib.auth.hashers import check_password
from django.db import connection
from radicale import auth as base_auth

from core.models import AppPassword, User


class Auth(base_auth.BaseAuth):
    def _login_ext(self, login: str, password: str, context) -> str:
        try:
            user = User.objects.filter(email__iexact=login, is_active=True).first()
            if user is None:
                return ""

            app_passwords = list(AppPassword.objects.filter(user=user))
            for app_pw in app_passwords:
                if check_password(password, app_pw.password_hash):
                    app_pw.last_used_at = datetime.now(timezone.utc)
                    app_pw.save(update_fields=["last_used_at"])
                    return login

            # Once app passwords exist, clients must use them; the account password is web-only.
            if not app_passwords and user.check_password(password):
                return login
            return ""
        finally:
            connection.close()
