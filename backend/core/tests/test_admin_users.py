"""
Superusers (the Django admin at /admin/): only `manage.py set_superuser` hands it out, not the app's
API; being superuser also lets the user sign in there (is_staff).
"""

import pytest
from django.core.management import CommandError, call_command

from core.models import User
from core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_api():
    admin = make_user("admin")
    admin.is_admin = True
    admin.save()
    return Api(admin)


def test_the_api_neither_shows_nor_sets_superuser(admin_api):
    res = admin_api.post("/admin/users", {
        "email": "new@example.test", "display_name": "New", "password": "password-1", "is_superuser": True,
    })
    assert res.status_code == 200, res.content
    assert "is_superuser" not in res.json()
    user = User.objects.get(email="new@example.test")
    assert not user.is_superuser and not user.is_staff

    res = admin_api.patch(f"/admin/users/{user.id}", {"is_superuser": True})
    assert res.status_code == 200, res.content
    user.refresh_from_db()
    assert not user.is_superuser


def test_set_superuser_hands_it_out_and_takes_it_away():
    user = make_user("someone")

    call_command("set_superuser", user.email.upper())
    user.refresh_from_db()
    assert user.is_superuser and user.is_staff

    call_command("set_superuser", user.email, "--revoke")
    user.refresh_from_db()
    assert not user.is_superuser and not user.is_staff


def test_set_superuser_needs_an_existing_user():
    with pytest.raises(CommandError):
        call_command("set_superuser", "nobody@example.test")


def test_staff_alone_is_not_kept():
    user = make_user("someone")
    user.is_staff = True
    user.save()

    user.refresh_from_db()
    assert not user.is_staff
