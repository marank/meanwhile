"""
Radicale auth plugin backed by Django users and app passwords.
"""

import functools
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.utils import timezone
from radicale import auth as base_auth

from core.models import AppPassword, User

# Checking a password is slow on purpose (Argon2), and CalDAV clients send it with every request.
# So the password hash a login's password last matched is remembered, by a keyed digest of the
# password; it counts only as long as that hash is still the user's (not deleted or changed).
_matched: dict[str, tuple[bytes, str]] = {}
_DIGEST_KEY = secrets.token_bytes(32)

# How exactly an app password's last use is kept; finer would mean a write on every request.
LAST_USED_PRECISION = timedelta(minutes=1)

# As for the web login (ACCOUNT_RATE_LIMITS): failed logins from one address for one login; once
# there were this many, even the right password is refused until the time is up.
MAX_FAILED_LOGINS = 10
FAILED_LOGINS_WINDOW = timedelta(minutes=5)


def _digest(login: str, password: str) -> bytes:
    return hmac.new(_DIGEST_KEY, f"{login}\0{password}".encode(), "sha256").digest()


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
    def _login_ext(self, login: str, password: str, context: base_auth.AuthContext) -> str:
        # REMOTE_ADDR: the client's address, also behind the proxy (uvicorn --proxy-headers).
        failures = _failures_key(login.lower(), getattr(context, "remote_addr", None))
        if cache.get(failures, 0) >= MAX_FAILED_LOGINS:
            return ""
        user = User.objects.filter(email__iexact=login, is_active=True).first()
        if user is None:
            # As long as checking a password, so the answer's time doesn't tell which accounts exist.
            check_password(password, _dummy_hash())
            _count_failure(failures)
            return ""
        app_passwords = list(AppPassword.objects.filter(user=user))
        # Once app passwords exist, clients must use them; the account password is web-only.
        candidates: dict[str, AppPassword | None] = (
            {p.password_hash: p for p in app_passwords} if app_passwords else {user.password: None}
        )

        key, digest = login.lower(), _digest(login.lower(), password)
        remembered = _matched.get(key)
        if remembered is not None and hmac.compare_digest(remembered[0], digest) and remembered[1] in candidates:
            matched = remembered[1]
        else:
            found = _matching_hash(user, app_passwords, password)
            if found is None:
                _count_failure(failures)
                return ""
            matched = found
            _matched[key] = (digest, matched)

        app_password = candidates.get(matched)  # None: the account password (its hash may just have been upgraded)
        now = timezone.now()
        if app_password is not None and (
            app_password.last_used_at is None or app_password.last_used_at < now - LAST_USED_PRECISION
        ):
            app_password.last_used_at = now
            app_password.save(update_fields=["last_used_at"])
        return login


@functools.cache
def _dummy_hash() -> str:
    return make_password(secrets.token_urlsafe(16))


def _matching_hash(user: User, app_passwords: list[AppPassword], password: str) -> str | None:
    if app_passwords:
        return next((p.password_hash for p in app_passwords if check_password(password, p.password_hash)), None)
    # check_password() upgrades the hash when the hasher's settings changed; the new one is kept.
    return user.password if user.check_password(password) else None
