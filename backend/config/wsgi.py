"""
WSGI config for the Calendar backend.

Mounts the embedded CalDAV server (Radicale) alongside the Django app.
"""

import os
from collections.abc import Iterable
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_application = get_wsgi_application()

# Import after Django apps are configured so settings/ORM access is safe.
from django.conf import settings  # noqa: E402

from core.caldav.app import create_application  # noqa: E402

radicale_application = create_application()

_caldav_prefix = settings.CALDAV_PATH.rstrip("/") or "/caldav"


class _PathDispatcher:
    """Minimal WSGI middleware that routes a path prefix to another app."""

    def __init__(self, default_app: WSGIApplication, mounts: dict[str, WSGIApplication]) -> None:
        self.default_app = default_app
        self.mounts = mounts

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        for prefix, app in self.mounts.items():
            if path == prefix or path.startswith(prefix + "/"):
                environ = environ.copy()
                environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
                environ["PATH_INFO"] = path[len(prefix) :]
                return app(environ, start_response)
        return self.default_app(environ, start_response)


application = _PathDispatcher(django_application, {_caldav_prefix: radicale_application})
