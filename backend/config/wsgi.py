"""
WSGI config for the Calendar backend.

Mounts the embedded CalDAV server (Radicale) alongside the Django app.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_application = get_wsgi_application()

# Import after Django apps are configured so settings/ORM access is safe.
from django.conf import settings  # noqa: E402
from radicale.app import Application as RadicaleApplication  # noqa: E402
from radicale.config import load as load_radicale_config  # noqa: E402

_radicale_config = load_radicale_config()
_radicale_config.update(
    {
        "auth": {"type": "core.caldav.auth"},
        "rights": {"type": "core.caldav.rights"},
        "storage": {"type": "core.caldav.storage"},
    },
    source="calendar-app-inline",
)
radicale_application = RadicaleApplication(_radicale_config)

_caldav_prefix = settings.CALDAV_PATH.rstrip("/") or "/caldav"


class _PathDispatcher:
    """Minimal WSGI middleware that routes a path prefix to another app."""

    def __init__(self, default_app, mounts: dict[str, object]) -> None:
        self.default_app = default_app
        self.mounts = mounts

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        for prefix, app in self.mounts.items():
            if path == prefix or path.startswith(prefix + "/"):
                environ = environ.copy()
                environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
                environ["PATH_INFO"] = path[len(prefix):]
                return app(environ, start_response)
        return self.default_app(environ, start_response)


application = _PathDispatcher(django_application, {_caldav_prefix: radicale_application})
