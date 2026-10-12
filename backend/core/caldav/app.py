"""
The Radicale WSGI application with the plugins of this app.
"""

from radicale import httputils
from radicale.app import Application as RadicaleApplication
from radicale.config import load as load_config

from core.caldav.request import request_scope
from core.caldav.storage import Forbidden


class Application(RadicaleApplication):
    def __call__(self, environ, start_response):
        # Radicale builds the whole response before it returns it.
        with request_scope():
            return super().__call__(environ, start_response)

    # Radicale answers errors raised by the storage with 500, except for PUT; refused writes get 403.
    def do_DELETE(self, *args, **kwargs):
        try:
            return super().do_DELETE(*args, **kwargs)
        except Forbidden:
            return httputils.FORBIDDEN

    def do_PROPPATCH(self, *args, **kwargs):
        try:
            return super().do_PROPPATCH(*args, **kwargs)
        except Forbidden:
            return httputils.FORBIDDEN


def create_application() -> Application:
    config = load_config()
    config.update(
        {
            "auth": {"type": "core.caldav.auth"},
            "rights": {"type": "core.caldav.rights"},
            "storage": {"type": "core.caldav.storage"},
        },
        source="calendar-app-inline",
    )
    return Application(config)
