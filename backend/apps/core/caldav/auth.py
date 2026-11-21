"""
Radicale auth plugin: CalDAV clients sign in with the account's email and one of its app passwords
(apps.core.services.app_passwords); the account password is for the web app only.
"""

import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from radicale import auth as base_auth

from apps.core.services import app_passwords

# How exactly an app password's last use is kept; finer would mean a write on every request.
LAST_USED_PRECISION = timedelta(minutes=1)

# As for the web login (ACCOUNT_RATE_LIMITS): failed logins from one address for one login; once
# there were this many, even the right app password is refused until the time is up.
MAX_FAILED_LOGINS = 10
FAILED_LOGINS_WINDOW = timedelta(minutes=5)


def _failures_key(login: str, address: str | None) -> str:
    return "caldav-failed-logins:" + hashlib.sha256(f"{address}\0{login}".encode()).hexdigest()


def _count_failure(key: str) -> None:
    # The window starts at the first failure: add() sets the count and its expiry, incr() keeps both.
    if not cache.add(key, 1, timeout=int(FAILED_LOGINS_WINDOW.total_seconds())):
        try:
            cache.incr(key)
        except ValueError:  # expired in between
            cache.add(key, 1, timeout=int(FAILED_LOGINS_WINDOW.total_seconds()))


class Auth(base_auth.BaseAuth):
    # Radicale passes what the client sent as the password; here that is always an app password's token.
    def _login_ext(self, login: str, token: str, context: base_auth.AuthContext) -> str:
        # REMOTE_ADDR: the client's address, also behind the proxy (uvicorn --proxy-headers).
        failures = _failures_key(login.lower(), getattr(context, "remote_addr", None))
        if cache.get(failures, 0) >= MAX_FAILED_LOGINS:
            return ""
        app_password = app_passwords.find(login, token)
        if app_password is None:
            _count_failure(failures)
            return ""
        now = timezone.now()
        if app_password.last_used_at is None or app_password.last_used_at < now - LAST_USED_PRECISION:
            app_password.last_used_at = now
            app_password.save(update_fields=["last_used_at"])
        return login
