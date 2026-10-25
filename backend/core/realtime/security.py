"""
Who may open a WebSocket: browsers on the app's own pages only.
"""

from urllib.parse import urlsplit

from asgiref.typing import ASGI3Application, ASGIReceiveCallable, ASGISendCallable, Scope, WebSocketCloseEvent
from django.conf import settings


def _origin_allowed(origin: str, host: str) -> bool:
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    # The page and the socket come from the same server (also behind a reverse proxy, which keeps
    # the Host header), or the page is a trusted one, like the Vite dev server in front of it.
    if parsed.netloc.lower() == host.lower():
        return True
    trusted = {o.rstrip("/").lower() for o in settings.CSRF_TRUSTED_ORIGINS}
    return f"{parsed.scheme}://{parsed.netloc}".lower() in trusted


class OriginCheck:
    """Refuses WebSockets opened by pages of other sites (cross-site WebSocket hijacking).

    The session cookie goes along with any page's WebSocket, so without this check another
    site could listen in on a signed-in user's updates. Clients that aren't browsers send no
    Origin; they still need the session cookie.
    """

    def __init__(self, app: ASGI3Application) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        headers = dict(scope["headers"]) if scope["type"] != "lifespan" else {}
        origin = headers.get(b"origin", b"").decode("latin1")
        # nginx passes the host the client asked for, a trusted proxy's X-Forwarded-Host included.
        host = headers.get(b"host", b"").decode("latin1").split(",")[0].strip()
        if origin and not _origin_allowed(origin, host):
            # The ASGI spec makes the reason optional; asgiref's types require it.
            close: WebSocketCloseEvent = {"type": "websocket.close", "code": 4403}  # type: ignore[typeddict-item]
            await send(close)
            return
        await self.app(scope, receive, send)
