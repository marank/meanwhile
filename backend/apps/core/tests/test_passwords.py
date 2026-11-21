"""
Passwords: changed in the account settings, or set anew from a link sent by email.
"""

import re
from typing import Any

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import Client
from pytest_django.fixtures import Settings

from apps.core.tests.helpers import Response, make_user

pytestmark = pytest.mark.django_db


def post(client: Client, url: str, data: dict[str, Any]) -> Response:
    return client.post(url, data, content_type="application/json")


def test_users_change_their_password_and_stay_signed_in() -> None:
    user = make_user("someone")
    client = Client()
    client.force_login(user)

    wrong = post(
        client, "/api/auth/v1/account/password/change", {"current_password": "nope", "new_password": "N3w-secret!"}
    )
    assert wrong.status_code == 400
    res = post(client, "/api/auth/v1/account/password/change", {"current_password": "x", "new_password": "N3w-secret!"})
    assert res.status_code == 200, res.content
    user.refresh_from_db()
    assert user.check_password("N3w-secret!")
    assert client.get("/api/users/me").status_code == 200


def request_link(email: str) -> str | None:
    """The key in the link mailed for `email`, if one was."""
    res = post(Client(), "/api/auth/v1/auth/password/request", {"email": email})
    assert res.status_code == 200, res.content
    if not mail.outbox:
        return None
    message = mail.outbox[-1]
    # From the app, not the Django site.
    body = str(message.body)
    assert "example.com" not in str(message.subject) + body
    match = re.search(r"https?://\S+/reset-password/(\S+)", body)
    assert match is not None
    return match.group(1)


def test_a_forgotten_password_is_set_anew_from_the_link_on_any_device(settings: Settings) -> None:
    user = make_user("someone")
    key = request_link("SOMEONE@example.test")
    assert mail.outbox[0].to == ["someone@example.test"]
    assert settings.HEADLESS_FRONTEND_URLS["account_reset_password_from_key"].split("{")[0] in mail.outbox[0].body

    # In another browser than the one that asked for it.
    other = Client()
    assert other.get("/api/auth/v1/auth/password/reset", HTTP_X_PASSWORD_RESET_KEY=key).status_code == 200
    res = post(other, "/api/auth/v1/auth/password/reset", {"key": key, "password": "N3w-secret!"})
    assert res.status_code in (200, 401), res.content  # 401: done, now sign in
    user.refresh_from_db()
    assert user.check_password("N3w-secret!")
    # The link works once.
    assert (
        post(Client(), "/api/auth/v1/auth/password/reset", {"key": key, "password": "An0ther-one!"}).status_code == 400
    )


def test_the_link_comes_like_the_apps_other_emails(settings: Settings) -> None:
    make_user("someone")
    key = request_link("someone@example.test")
    [message] = mail.outbox
    assert isinstance(message, EmailMultiAlternatives)
    assert message.subject == "Reset your password for Meanwhile"
    html = next(str(content) for content, mimetype in message.alternatives if mimetype == "text/html")
    assert 'class="mw-heading"' in html and f"/reset-password/{key}" in html and "Choose new password" in html


def test_made_up_keys_change_nothing(settings: Settings) -> None:
    user = make_user("someone")
    for key in ("nonsense", f"{user.pk.hex}-abc-def", "x-y"):
        assert (
            post(Client(), "/api/auth/v1/auth/password/reset", {"key": key, "password": "N3w-secret!"}).status_code
            == 400
        )
    user.refresh_from_db()
    assert user.check_password("x")


def test_unknown_addresses_get_no_mail_and_the_same_answer(settings: Settings) -> None:
    assert request_link("nobody@example.test") is None


def test_the_link_comes_in_the_accounts_language(settings: Settings) -> None:
    user = make_user("someone")
    user.language = "de"
    user.save()
    request_link("someone@example.test")
    assert "Passwort" in mail.outbox[0].subject
