from django.conf import settings
from django.urls import path

from core.realtime.consumers import LiveUpdatesConsumer

websocket_urlpatterns = [
    path(settings.WEBSOCKET_PATH.lstrip("/"), LiveUpdatesConsumer.as_asgi()),
]
