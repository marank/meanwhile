"""
Telling connected clients that something changed.

Messages only say *that* a calendar's events or a user's notifications changed, never what: each
client loads the data again through the API, which applies that user's permissions (e.g. who
may see a pending booking). They go out after the transaction commits, so clients never load
data that isn't there yet, and changes of one transaction (deleting a calendar with all its
events) are sent once.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def calendar_group(calendar_id) -> str:
    return f"calendar.{calendar_id}"


def user_group(user_id) -> str:
    return f"user.{user_id}"


def calendar_changed(calendar_id) -> None:
    """The events of the calendar changed."""
    if calendar_id:
        _queue(calendar_group(calendar_id), {"type": "calendar.changed", "calendar_id": str(calendar_id)})


def notifications_changed(user_id) -> None:
    """The user has new or changed notifications."""
    if user_id:
        _queue(user_group(user_id), {"type": "notifications.changed"})


def calendars_changed(user_ids) -> None:
    """The users' lists of calendars and folders changed (access, names, colors, order)."""
    for user_id in set(user_ids):
        if user_id:
            _queue(user_group(user_id), {"type": "calendars.changed"})


def reminders_due(user_id, reminders: list[dict]) -> None:
    """Reminders of the user came due: their tabs show them."""
    if user_id and reminders:
        _queue(user_group(user_id), {"type": "reminders.due", "reminders": reminders})


def _queue(group: str, message: dict) -> None:
    # Kept by group and type: one message of each kind per transaction, none taking another's place.
    key = (group, message["type"])
    connection = transaction.get_connection()
    if not connection.in_atomic_block:
        _send({key: message})
        return
    # One batch per transaction, sent once it commits. A batch whose callback Django dropped
    # (its savepoint was rolled back) is replaced, so later changes still go out.
    batch = getattr(connection, "_live_updates", None)
    if batch is None or not any(entry[1] is batch["flush"] for entry in connection.run_on_commit):
        messages: dict[tuple[str, str], dict] = {}

        def flush() -> None:
            connection._live_updates = None
            _send(messages)

        batch = connection._live_updates = {"messages": messages, "flush": flush}
        transaction.on_commit(flush, robust=True)
    batch["messages"][key] = message


def _send(messages: dict[tuple[str, str], dict]) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    for (group, _), message in messages.items():
        try:
            async_to_sync(layer.group_send)(group, message)
        except Exception:
            # Live updates are a convenience: a missing Redis must not break saving.
            logger.warning("Could not send live update to %s", group, exc_info=True)
