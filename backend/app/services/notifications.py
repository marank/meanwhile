from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models import Notification


def notify(
    db: Session,
    recipient_ids: Iterable[Optional[str]],
    type: str,
    actor_id: Optional[str],
    title: str,
    calendar_id: Optional[str] = None,
    event_id: Optional[str] = None,
    data: Optional[dict] = None,
) -> None:
    seen = set()
    for recipient_id in recipient_ids:
        if recipient_id is None or recipient_id == actor_id or recipient_id in seen:
            continue
        seen.add(recipient_id)
        db.add(
            Notification(
                user_id=recipient_id,
                type=type,
                actor_id=actor_id,
                calendar_id=calendar_id,
                event_id=event_id,
                title=title,
                data=data,
            )
        )
