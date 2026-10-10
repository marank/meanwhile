"""
Notification creation helper.
"""

from core.models.events import Notification


def notify(
    recipient_ids,
    type: str,
    actor_id: str | None,
    title: str,
    calendar_id: str | None = None,
    event_id: str | None = None,
    data: dict | None = None,
) -> None:
    seen = set()
    for recipient_id in recipient_ids:
        if recipient_id is None or recipient_id == actor_id or recipient_id in seen:
            continue
        seen.add(recipient_id)
        Notification.objects.create(
            user_id=recipient_id,
            type=type,
            actor_id=actor_id,
            calendar_id=calendar_id,
            event_id=event_id,
            title=title,
            data=data,
        )
