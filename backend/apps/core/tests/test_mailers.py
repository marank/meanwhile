"""
The mailer (Django's MAILERS) comes from the EMAIL_* variables of .env.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]

SHOW_MAILER = """
import json, django
django.setup()
from django.core.mail import mailers
mailer = mailers.default
print(json.dumps({
    "backend": type(mailer).__module__,
    "smtp": [getattr(mailer, name, None) for name in ("host", "port", "username", "use_tls", "use_ssl", "timeout")],
}))
"""


def mailer_with(**variables: str) -> dict[str, object]:
    """The default mailer as the settings make it from these variables (in a fresh process)."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DEBUG": "true",
        "EMAIL_HOST": "",
        **variables,
    }
    result = subprocess.run(
        [sys.executable, "-c", SHOW_MAILER], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, check=True
    )
    shown: dict[str, object] = json.loads(result.stdout.splitlines()[-1])
    return shown


def test_with_a_mail_server_emails_go_out_through_it() -> None:
    mailer = mailer_with(EMAIL_HOST="smtp.example.test", EMAIL_PORT="465", EMAIL_HOST_USER="app", EMAIL_USE_SSL="true")
    assert mailer["backend"] == "django.core.mail.backends.smtp"
    assert mailer["smtp"] == ["smtp.example.test", 465, "app", False, True, 15]


def test_without_a_mail_server_development_prints_them() -> None:
    assert mailer_with()["backend"] == "django.core.mail.backends.console"


def test_without_a_mail_server_production_drops_them() -> None:
    assert mailer_with(DEBUG="false", SECRET_KEY="x" * 50)["backend"] == "django.core.mail.backends.dummy"
