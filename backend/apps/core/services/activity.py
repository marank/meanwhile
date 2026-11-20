"""
Event activity log helper.
"""

from typing import Any

from apps.core.models.events import Event, EventActivity


def record_activity(
    event: Event,
    actor_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> EventActivity:
    return EventActivity.objects.create(
        event=event,
        actor_id=actor_id,
        action=action,
        details=details,
    )
