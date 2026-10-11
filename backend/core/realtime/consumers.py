"""
The WebSocket endpoint for live updates.

Protocol (JSON messages):

client → server
    {"type": "ping"}                                   keep-alive; answered with "pong"
    {"type": "subscribe", "calendars": ["<id>", ...]}  the calendars shown now (replaces earlier ones)

server → client
    {"type": "hello", "protocol": 1}                   after connecting
    {"type": "pong"}
    {"type": "subscribed", "calendars": [...]}         the calendars the user may follow
    {"type": "events.changed", "calendar_id": "<id>"}  load that calendar's events again
    {"type": "notifications.changed"}                  load the notifications again
    {"type": "calendars.changed"}                      load the list of calendars and folders again
    {"type": "error", "message": "..."}

The connection closes with 4401 when the session is missing or has ended; clients then stop
reconnecting until the user signs in again.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.sessions.backends.base import SessionBase

from core.models import Calendar, User
from core.realtime.broadcast import calendar_group, user_group
from core.services.permissions import get_membership

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
CLOSE_UNAUTHENTICATED = 4401
# A client follows the calendars on screen; more than this is not a client of this app.
MAX_SUBSCRIPTIONS = 200
MAX_MESSAGE_BYTES = 16 * 1024


@database_sync_to_async
def _readable_calendars(user: User, calendar_ids: list[str]) -> set[str]:
    if not user.is_active:
        return set()
    return {
        str(calendar.id)
        for calendar in Calendar.objects.filter(id__in=calendar_ids)
        if get_membership(calendar, user) is not None
    }


@database_sync_to_async
def _session_valid(session: SessionBase | None, user: User) -> bool:
    """Whether the sign-in the connection was opened with still holds (no logout, account active)."""
    if session is None or not session.session_key or not session.exists(session.session_key):
        return False
    return User.objects.filter(pk=user.pk, is_active=True).exists()


class LiveUpdatesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.calendars: set[str] = set()
        self.groups_joined: set[str] = set()
        if self.user is None or not self.user.is_authenticated or not self.user.is_active:
            # Accept first so the browser sees the close code instead of a failed handshake.
            await self.accept()
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        await self._join(user_group(self.user.pk))
        await self.accept()
        await self._send({"type": "hello", "protocol": PROTOCOL_VERSION})

    async def disconnect(self, code):
        for group in list(self.groups_joined):
            await self._leave(group)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None or len(text_data) > MAX_MESSAGE_BYTES:
            await self._send({"type": "error", "message": "Expected a JSON text message"})
            return
        try:
            message = json.loads(text_data)
        except ValueError:
            await self._send({"type": "error", "message": "Invalid JSON"})
            return
        kind = message.get("type") if isinstance(message, dict) else None
        if kind == "ping":
            await self._ping()
        elif kind == "subscribe":
            await self._subscribe(message.get("calendars"))
        else:
            await self._send({"type": "error", "message": f"Unknown message type {kind!r}"})

    async def _ping(self):
        if not await _session_valid(self.scope.get("session"), self.user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        await self._send({"type": "pong"})

    async def _subscribe(self, calendar_ids):
        if not isinstance(calendar_ids, list) or not all(isinstance(i, str) for i in calendar_ids):
            await self._send({"type": "error", "message": "calendars must be a list of ids"})
            return
        wanted = await _readable_calendars(self.user, list(dict.fromkeys(calendar_ids))[:MAX_SUBSCRIPTIONS])
        for calendar_id in self.calendars - wanted:
            await self._leave(calendar_group(calendar_id))
        for calendar_id in wanted - self.calendars:
            await self._join(calendar_group(calendar_id))
        self.calendars = wanted
        await self._send({"type": "subscribed", "calendars": sorted(wanted)})

    # Group messages (sent by core.realtime.broadcast) ---------------------------------------

    async def calendar_changed(self, message):
        calendar_id = message["calendar_id"]
        if calendar_id not in self.calendars:
            return
        # Access may have ended since subscribing (left the calendar, account deactivated).
        if calendar_id not in await _readable_calendars(self.user, [calendar_id]):
            self.calendars.discard(calendar_id)
            await self._leave(calendar_group(calendar_id))
            await self._send({"type": "subscribed", "calendars": sorted(self.calendars)})
            return
        await self._send({"type": "events.changed", "calendar_id": calendar_id})

    async def notifications_changed(self, message):
        await self._send({"type": "notifications.changed"})

    async def calendars_changed(self, message):
        await self._send({"type": "calendars.changed"})

    # Helpers -------------------------------------------------------------------------------

    async def _send(self, message: dict):
        await self.send(text_data=json.dumps(message))

    async def _join(self, group: str):
        await self.channel_layer.group_add(group, self.channel_name)
        self.groups_joined.add(group)

    async def _leave(self, group: str):
        await self.channel_layer.group_discard(group, self.channel_name)
        self.groups_joined.discard(group)
