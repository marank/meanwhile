"""
Django's permissions alongside the app's own groups (User.groups are UserGroups, not auth.Groups).
"""

import importlib

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.test import Client

from core.models import UserGroup
from core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


def test_users_in_groups_have_just_their_own_permissions() -> None:
    user = make_user("member")
    UserGroup.objects.create(name="Family").user_set.add(user)
    user.user_permissions.add(Permission.objects.get(codename="view_calendar"))
    assert user.get_all_permissions() == {"core.view_calendar"}
    assert user.has_perm("core.view_calendar") and not user.has_perm("core.change_calendar")


def test_the_admin_turns_away_users_who_are_not_superusers(client: Client) -> None:
    client.force_login(make_user("member"))
    res = client.get("/django-admin/login/")
    assert res.status_code == 200 and b"not authorized to access this page" in res.content


def test_the_django_admin_leaves_admin_to_the_apps_page(client: Client) -> None:
    # /admin is the SPA's administration page; nginx serves index.html for it.
    assert client.get("/django-admin/login/").status_code == 200
    assert client.get("/admin/").status_code == 404
    assert client.get("/admin/login/").status_code == 404


def test_sessions_from_before_the_backend_changed_stay_signed_in() -> None:
    # Signed in when Django's ModelBackend was configured; the migration moves the session over.
    old = Client()
    old.force_login(make_user("before"), backend="django.contrib.auth.backends.ModelBackend")
    assert old.get("/api/users/me").status_code == 401
    migration = importlib.import_module("core.migrations.0002_sessions_keep_their_backend")
    migration.move_sessions(apps, None)
    assert old.get("/api/users/me").status_code == 200
