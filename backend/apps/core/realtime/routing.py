from django.conf import settings
from django.urls import path

from apps.core.realtime.consumers import LiveUpdatesConsumer

websocket_urlpatterns = [
    # django-stubs' path() takes views only; Channels routes ASGI applications with it too.
    path(settings.WEBSOCKET_PATH.lstrip("/"), LiveUpdatesConsumer.as_asgi()),  # type: ignore[arg-type]
]
