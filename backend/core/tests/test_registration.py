"""
Signing up: open or closed with ALLOW_REGISTRATION, and the login page told which.
"""

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

from core.models import User

pytestmark = pytest.mark.django_db


def sign_up(client: Client) -> int:
    res = client.post(
        "/api/auth/v1/auth/signup",
        {"email": "new@example.test", "display_name": "New", "password": "correct horse battery"},
        content_type="application/json",
    )
    return res.status_code


@pytest.mark.parametrize("allowed", [True, False])
def test_the_public_settings_say_whether_anyone_may_sign_up(client: Client, settings: Settings, allowed: bool) -> None:
    settings.ALLOW_REGISTRATION = allowed
    assert client.get("/api/settings").json()["allow_registration"] is allowed


def test_with_registration_closed_nobody_can_sign_up(client: Client, settings: Settings) -> None:
    settings.ALLOW_REGISTRATION = False
    assert sign_up(client) == 403
    assert not User.objects.filter(email="new@example.test").exists()


def test_with_registration_open_anyone_can_sign_up(client: Client, settings: Settings) -> None:
    settings.ALLOW_REGISTRATION = True
    assert sign_up(client) == 200
    assert User.objects.filter(email="new@example.test").exists()
