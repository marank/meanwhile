"""
allauth sends no emails of its own: they would be plain text in its wording, unlike the app's. The
one it needs, the password reset link, is the app's own email (test_passwords).
"""

import pytest
from django.core.mail import EmailMessage
from django.test import Client
from pytest_django.fixtures import Settings

from apps.core.adapters import AccountAdapter
from apps.core.tests.helpers import make_user

pytestmark = pytest.mark.django_db


def test_allauths_own_emails_are_dropped(mailoutbox: list[EmailMessage], caplog: pytest.LogCaptureFixture) -> None:
    user = make_user("anna")
    AccountAdapter().send_mail("account/email/password_changed", user.email, {})
    assert mailoutbox == []
    assert "Not sending allauth's own email account/email/password_changed" in caplog.text
    # Who it was for stays out of the log.
    assert user.email not in caplog.text


def test_the_account_flows_send_no_allauth_email(
    mailoutbox: list[EmailMessage], caplog: pytest.LogCaptureFixture, settings: Settings
) -> None:
    settings.ALLOW_REGISTRATION = True
    make_user("anna")

    def post(client: Client, url: str, data: dict[str, str]) -> None:
        client.post(f"/api/auth/v1{url}", data, content_type="application/json")

    post(Client(), "/auth/signup", {"email": "new@example.test", "password": "N3w-secret!x", "display_name": "N"})
    post(Client(), "/auth/signup", {"email": "anna@example.test", "password": "N3w-secret!x", "display_name": "A"})
    post(Client(), "/auth/password/request", {"email": "nobody@example.test"})
    signed_in = Client()
    signed_in.force_login(make_user("bert"))
    post(signed_in, "/account/password/change", {"current_password": "x", "new_password": "N3w-secret!x"})
    assert mailoutbox == []
    # Not even dropped ones: the settings keep allauth from trying.
    assert "allauth" not in caplog.text
