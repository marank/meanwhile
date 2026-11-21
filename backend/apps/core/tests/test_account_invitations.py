"""
Accounts an admin creates, with or without a password, and the email that invites their owner in.
"""

import re

import pytest
from django.core import mail
from django.test import Client
from pytest_django.fixtures import Settings

from apps.core.models import User
from apps.core.tests.helpers import Api, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_api(settings: Settings) -> Api:
    admin = make_user("admin")
    admin.is_admin = True
    admin.display_name = "Ada Admin"
    admin.save()
    return Api(admin)


def create(api: Api, **fields: object) -> User:
    res = api.post("/admin/users", {"email": "new@example.test", "display_name": "New", **fields})
    assert res.status_code == 200, res.content
    return User.objects.get(id=res.json()["id"])


def sign_in(email: str, password: str) -> int:
    res = Client().post(
        "/api/auth/v1/auth/login", {"email": email, "password": password}, content_type="application/json"
    )
    return res.status_code


def test_users_are_created_without_password_and_get_no_mail_unasked(admin_api: Api) -> None:
    user = create(admin_api)
    assert not user.has_usable_password()
    assert mail.outbox == []
    [listed] = [u for u in admin_api.get("/admin/users").json() if u["id"] == str(user.id)]
    assert listed["has_password"] is False


def test_the_invitation_lets_users_without_password_choose_one(admin_api: Api) -> None:
    user = create(admin_api)
    assert admin_api.post(f"/admin/users/{user.id}/invite").status_code == 200

    [message] = mail.outbox
    assert message.to == ["new@example.test"]
    assert "Ada Admin" in str(message.body)
    match = re.search(r"https?://\S+/reset-password/([^\s?]+)\?invite=1", str(message.body))
    assert match is not None
    key = match.group(1)

    res = Client().post(
        "/api/auth/v1/auth/password/reset",
        {"key": key, "password": "N3w-secret!"},
        content_type="application/json",
    )
    assert res.status_code in (200, 401), res.content  # 401: done, now sign in
    assert sign_in("new@example.test", "N3w-secret!") == 200
    # The link works once.
    res = Client().post(
        "/api/auth/v1/auth/password/reset",
        {"key": key, "password": "An0ther-one!"},
        content_type="application/json",
    )
    assert res.status_code == 400


def test_users_with_a_password_are_asked_to_sign_in(admin_api: Api) -> None:
    user = create(admin_api, password="given-password-1")
    assert admin_api.get(f"/admin/users/{user.id}").json()["has_password"] is True
    assert sign_in("new@example.test", "given-password-1") == 200
    assert admin_api.post(f"/admin/users/{user.id}/invite").status_code == 200

    [message] = mail.outbox
    body = str(message.body)
    assert "/login" in body and "/reset-password/" not in body
    assert "given-password-1" not in body


def test_the_invitation_comes_in_the_admins_language_until_the_user_has_one(admin_api: Api) -> None:
    admin_api.user.language = "de"
    admin_api.user.save()
    user = create(admin_api)
    admin_api.post(f"/admin/users/{user.id}/invite")
    assert "Einladung" in str(mail.outbox[-1].subject)

    user.language = "en"
    user.save()
    admin_api.post(f"/admin/users/{user.id}/invite")
    assert "invited" in str(mail.outbox[-1].subject)


def test_only_admins_invite_and_never_superusers(admin_api: Api) -> None:
    user = make_user("someone")
    assert Api(user).post(f"/admin/users/{user.id}/invite").status_code == 403
    boss = make_user("boss")
    boss.is_superuser = True
    boss.save()
    assert admin_api.post(f"/admin/users/{boss.id}/invite").status_code == 403
    assert mail.outbox == []
