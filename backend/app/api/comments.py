from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Event, EventActivity, EventComment, Role, User
from app.schemas import ActivityOut, CommentCreate, CommentOut
from app.services.notifications import notify
from app.services.permissions import (
    get_visible_event,
    has_at_least_role,
    require_membership,
)

router = APIRouter(prefix="/calendars", tags=["comments"])


def _serialize_comment(comment: EventComment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        event_id=comment.event_id,
        author_id=comment.author_id,
        author_name=comment.author.display_name if comment.author else "",
        body=comment.body,
        created_at=comment.created_at,
    )


@router.get("/events/{event_id}/comments", response_model=List[CommentOut])
def list_comments(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CommentOut]:
    event, _ = get_visible_event(db, event_id, current_user)
    comments = (
        db.query(EventComment)
        .filter(EventComment.event_id == event.id)
        .order_by(EventComment.created_at.asc())
        .all()
    )
    return [_serialize_comment(c) for c in comments]


@router.post(
    "/events/{event_id}/comments", response_model=CommentOut, status_code=201
)
def create_comment(
    event_id: str,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentOut:
    event, membership = get_visible_event(db, event_id, current_user)
    if not has_at_least_role(membership, Role.CONTRIBUTOR):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to comment",
        )
    body = data.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Comment must not be empty")
    comment = EventComment(
        event_id=event.id,
        author_id=current_user.id,
        body=body,
    )
    db.add(comment)
    db.flush()
    previous_commenters = (
        db.query(EventComment.author_id)
        .filter(EventComment.event_id == event.id)
        .distinct()
        .all()
    )
    notify(
        db,
        [event.creator_id] + [row.author_id for row in previous_commenters],
        "comment_added",
        current_user.id,
        event.title,
        calendar_id=event.calendar_id,
        event_id=event.id,
    )
    db.commit()
    db.refresh(comment)
    return _serialize_comment(comment)


@router.delete("/events/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    comment = db.query(EventComment).filter(EventComment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    event = db.query(Event).filter(Event.id == comment.event_id).first()
    membership = require_membership(db, event.calendar_id, current_user.id)
    if comment.author_id != current_user.id and not has_at_least_role(
        membership, Role.EDITOR
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this comment",
        )
    db.delete(comment)
    db.commit()


@router.get("/events/{event_id}/activity", response_model=List[ActivityOut])
def list_activity(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ActivityOut]:
    event, _ = get_visible_event(db, event_id, current_user)
    entries = (
        db.query(EventActivity)
        .filter(EventActivity.event_id == event.id)
        .order_by(EventActivity.created_at.asc())
        .all()
    )
    return [
        ActivityOut(
            id=entry.id,
            event_id=entry.event_id,
            actor_id=entry.actor_id,
            actor_name=entry.actor.display_name if entry.actor else None,
            action=entry.action,
            details=entry.details,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
