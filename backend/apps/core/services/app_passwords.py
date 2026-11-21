"""
App passwords: what CalDAV clients sign in with (the account password is for the web app only).

They are random tokens the app makes, 256 bits each, so nobody can guess one; a slow password hash
(Argon2), which protects passwords people make up, would only cost time on every CalDAV request.
They are kept as their SHA-256, looked up directly, as API tokens commonly are.
"""

import hashlib
import secrets

from apps.core.models import AppPassword, User

TOKEN_BYTES = 32


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(user: User, label: str) -> tuple[AppPassword, str]:
    """A new app password for the user and its token, which is shown once and not kept."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return AppPassword.objects.create(user=user, label=label, token_hash=token_hash(token)), token


def find(login: str, token: str) -> AppPassword | None:
    """The app password `token` is, if it belongs to the active user signing in as `login`."""
    return (
        AppPassword.objects.select_related("user")
        .filter(token_hash=token_hash(token), user__email__iexact=login, user__is_active=True)
        .first()
    )
