from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Calendar, Event, EventStatus
from app.services.ical import build_calendar_feed

router = APIRouter(prefix="", tags=["feed"])


@router.get("/{feed_token}.ics")
def calendar_feed(
    feed_token: str,
    db: Session = Depends(get_db),
) -> Response:
    calendar = (
        db.query(Calendar).filter(Calendar.feed_token == feed_token).first()
    )
    if calendar is None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    events = (
        db.query(Event)
        .filter(
            Event.calendar_id == calendar.id,
            Event.status.in_(
                {EventStatus.CONFIRMED.value, EventStatus.APPROVED.value}
            ),
        )
        .all()
    )
    body = build_calendar_feed(events)
    return Response(content=body, media_type="text/calendar")
