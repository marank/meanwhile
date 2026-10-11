"""
ASGI entry point: the app and its API, the CalDAV server, and the WebSocket for live updates.

Development: `manage.py runserver` serves it (through daphne). Production: run it with uvicorn,
e.g. `uvicorn config.asgi:application`.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django must be set up before anything touches models.
django_application = get_asgi_application()

from a2wsgi import WSGIMiddleware  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.conf import settings  # noqa: E402

from core.caldav.app import create_application  # noqa: E402
from core.realtime.routing import websocket_urlpatterns  # noqa: E402
from core.realtime.security import OriginCheck  # noqa: E402

_caldav_prefix = settings.CALDAV_PATH.rstrip("/") or "/caldav"
# Radicale is a WSGI application; its requests run in a thread pool, so a slow one (e.g. the
# delay after a failed login) doesn't hold up the other requests.
_caldav_application = WSGIMiddleware(create_application(), workers=20)


async def http_application(scope, receive, send):
    """Requests under the CalDAV prefix go to Radicale, mounted there; all others to Django."""
    path = scope["path"]
    if path == _caldav_prefix or path.startswith(_caldav_prefix + "/"):
        scope = {**scope, "root_path": scope.get("root_path", "") + _caldav_prefix}
        return await _caldav_application(scope, receive, send)
    return await django_application(scope, receive, send)


application = ProtocolTypeRouter(
    {
        "http": http_application,
        "websocket": OriginCheck(AuthMiddlewareStack(URLRouter(websocket_urlpatterns))),
    }
)
