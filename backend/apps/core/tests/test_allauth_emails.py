"""
allauth's own emails go out like the app's: as jobs after the commit, not inside the request.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.core.mail import EmailMessage
from pytest_django.fixtures import Settings

from apps.core.adapters import AccountAdapter
from apps.core.tests.helpers import make_user

pytestmark = pytest.mark.django_db

type CaptureCallbacks = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


def test_allauths_emails_are_sent_after_the_commit(
    settings: Settings, mailoutbox: list[EmailMessage], django_capture_on_commit_callbacks: CaptureCallbacks
) -> None:
    # As in production (the tests' default sends at once), natively without a queue.
    settings.EMAIL_SEND_IN_BACKGROUND = True
    settings.JOB_QUEUE = False
    user = make_user("anna")
    with django_capture_on_commit_callbacks(execute=True):
        AccountAdapter().send_mail("account/email/unknown_account", user.email, {"signup_url": "http://x/"})
        assert mailoutbox == []
    assert [message.to for message in mailoutbox] == [[user.email]]
    assert mailoutbox[0].subject.startswith("[")
