"""
Passwords: changed in the account settings, or set anew with a code sent by email.
"""

import re

import pytest
from django.core import mail
from django.test import Client

from core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


def post(client: Client, url: str, data: dict):
    return client.post(url, data, content_type="application/json")


def test_users_change_their_password_and_stay_signed_in():
    user = make_user("someone")
    client = Client()
    client.force_login(user)

    wrong = post(client, "/api/auth/v1/account/password/change", {"current_password": "nope", "new_password": "N3w-secret!"})
    assert wrong.status_code == 400
    res = post(client, "/api/auth/v1/account/password/change", {"current_password": "x", "new_password": "N3w-secret!"})
    assert res.status_code == 200, res.content
    user.refresh_from_db()
    assert user.check_password("N3w-secret!")
    assert client.get("/api/users/me").status_code == 200


def request_code(client: Client, email: str) -> str | None:
    res = post(client, "/api/auth/v1/auth/password/request", {"email": email})
    # 401: the reset by code is under way and waits for the code.
    assert res.status_code == 401, res.content
    if not mail.outbox:
        return None
    message = mail.outbox[-1]
    # From the app, not the Django site.
    assert "example.com" not in message.subject + message.body
    # The code stands on a line of its own after the request to enter it.
    return re.search(r"browser window\.\s+(\S+)", message.body).group(1)


def test_a_forgotten_password_is_set_anew_with_the_code(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = make_user("someone")
    client = Client()

    code = request_code(client, "SOMEONE@example.test")
    assert mail.outbox[0].to == ["someone@example.test"]
    res = post(client, "/api/auth/v1/auth/password/reset", {"key": code, "password": "N3w-secret!"})
    assert res.status_code in (200, 401), res.content  # 401: done, now sign in
    user.refresh_from_db()
    assert user.check_password("N3w-secret!")


def test_wrong_codes_and_other_sessions_change_nothing(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = make_user("someone")
    client = Client()
    code = request_code(client, "someone@example.test")

    assert post(Client(), "/api/auth/v1/auth/password/reset", {"key": code, "password": "N3w-secret!"}).status_code >= 400
    assert post(client, "/api/auth/v1/auth/password/reset", {"key": "WRONG1", "password": "N3w-secret!"}).status_code == 400
    user.refresh_from_db()
    assert user.check_password("x")


def test_unknown_addresses_get_no_mail_and_the_same_answer(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    assert request_code(Client(), "nobody@example.test") is None


def test_the_code_comes_in_the_accounts_language(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = make_user("someone")
    user.language = "de"
    user.save()
    post(Client(), "/api/auth/v1/auth/password/request", {"email": "someone@example.test"})
    assert "Passwort" in mail.outbox[0].subject
