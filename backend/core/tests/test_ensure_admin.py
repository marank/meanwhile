"""
`manage.py ensure_admin`: the admin user of ADMIN_EMAIL, created or updated on every start.
"""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import SESSION_KEY
from django.core.management import CommandError, call_command
from django.test import Client

from core.models import OverviewSettings, User
from core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_env(settings):
    settings.ADMIN_EMAIL = "Admin@Example.test"
    settings.ADMIN_PASSWORD = "secret-1"
    settings.ADMIN_NAME = "Admin"
    return settings


def test_creates_the_admin(admin_env):
    call_command("ensure_admin")

    user = User.objects.get(email__iexact="admin@example.test")
    assert user.is_admin and user.is_staff and user.is_superuser and user.is_active
    assert user.check_password("secret-1")
    assert user.display_name == "Admin"
    assert EmailAddress.objects.filter(user=user, primary=True, verified=True).exists()
    # Their settings follow the app defaults, also those an admin sets after this.
    assert not OverviewSettings.objects.filter(user=user).exists()


def test_the_admin_can_sign_in(admin_env):
    call_command("ensure_admin")

    client = Client()
    res = client.post(
        "/api/auth/v1/auth/login",
        {"email": "admin@example.test", "password": "secret-1"},
        content_type="application/json",
    )
    assert res.status_code == 200, res.content
    assert SESSION_KEY in client.session


def test_promotes_an_existing_user_and_updates_password_and_name(admin_env):
    user = make_user("someone")
    admin_env.ADMIN_EMAIL = user.email.upper()

    call_command("ensure_admin")

    user.refresh_from_db()
    assert user.is_admin and user.is_staff and user.is_superuser
    assert user.check_password("secret-1")
    assert user.display_name == "Admin"
    assert User.objects.count() == 1


def test_an_unchanged_password_is_not_set_again(admin_env):
    """Setting it again would change its hash and so sign the admin out of every session."""
    call_command("ensure_admin")
    hash_before = User.objects.get().password

    call_command("ensure_admin")

    assert User.objects.get().password == hash_before


def test_without_a_password_an_existing_user_keeps_theirs(admin_env):
    user = make_user("someone")
    admin_env.ADMIN_EMAIL = user.email
    admin_env.ADMIN_PASSWORD = ""

    call_command("ensure_admin")

    user.refresh_from_db()
    assert user.is_admin
    assert user.check_password("x")


def test_a_new_admin_needs_a_password(admin_env):
    admin_env.ADMIN_PASSWORD = ""

    with pytest.raises(CommandError):
        call_command("ensure_admin")
    assert not User.objects.exists()


def test_without_admin_email_nothing_happens(admin_env):
    admin_env.ADMIN_EMAIL = ""

    call_command("ensure_admin")

    assert not User.objects.exists()
