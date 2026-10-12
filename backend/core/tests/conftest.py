import pytest

from core.services import mail


@pytest.fixture(autouse=True)
def send_emails_right_away(settings, monkeypatch):
    """Emails go out at once (tests run inside a transaction that never commits) and in the test's thread."""
    settings.EMAIL_SEND_IN_BACKGROUND = False
    settings.APP_URL = "http://app.test"
    settings.IMIP_ADDRESS = ""
    monkeypatch.setattr(mail, "_after_commit", lambda callback: callback())
