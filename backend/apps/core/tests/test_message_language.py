"""
The API answers in the language the SPA names in X-Language: its own errors, Django's password rules and
allauth's messages. The browser's Accept-Language decides nothing.
"""

import pytest
from django.test import Client

from apps.core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client() -> Client:
    admin = make_user("admin")
    admin.is_admin = True
    admin.save()
    client = Client()
    client.force_login(admin)
    return client


def add_existing_user(client: Client, **headers: str) -> str:
    make_user("taken")
    res = client.post(
        "/api/admin/users",
        {"email": "TAKEN@example.test", "display_name": "Taken"},
        content_type="application/json",
        headers=headers,
    )
    assert res.status_code == 400, res.content
    detail: str = res.json()["detail"]
    return detail


def test_the_apps_own_errors_come_in_the_named_language(admin_client: Client) -> None:
    assert (
        add_existing_user(admin_client, x_language="de") == "Es gibt bereits einen Benutzer mit dieser E-Mail-Adresse"
    )


@pytest.mark.parametrize("headers", [{}, {"accept_language": "de"}, {"x_language": "fr"}])
def test_without_a_named_language_they_stay_english(admin_client: Client, headers: dict[str, str]) -> None:
    assert add_existing_user(admin_client, **headers) == "A user with this email already exists"


def test_password_rules_come_in_the_named_language() -> None:
    client = Client()
    client.force_login(make_user("someone"))
    res = client.post(
        "/api/auth/v1/account/password/change",
        {"current_password": "x", "new_password": "48151623"},
        content_type="application/json",
        headers={"x_language": "de"},
    )
    assert res.status_code == 400, res.content
    messages = [error["message"].strip() for error in res.json()["errors"]]
    assert "Dieses Passwort ist komplett numerisch." in messages
