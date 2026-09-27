from typing import Optional

from sqlalchemy.orm import Session

from app.models import Event, EventActivity


def record_activity(
    db: Session,
    event: Event,
    actor_id: str,
    action: str,
    details: Optional[dict] = None,
) -> EventActivity:
    entry = EventActivity(
        event_id=event.id,
        actor_id=actor_id,
        action=action,
        details=details,
    )
    db.add(entry)
    return entry
