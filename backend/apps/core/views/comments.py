"""
Event comments and activity endpoints.
"""

from typing import Any

from ninja import Router
from ninja.errors import HttpError

from apps.core.models import EventActivity, EventComment
from apps.core.models.base import Role
from apps.core.schemas import ActivityOut, CommentCreate, CommentOut, OkOut
from apps.core.services import comments
from apps.core.services.permissions import get_membership, get_visible_event, has_at_least_role
from apps.core.views.common import AuthedRequest

router = Router()


def _serialize_comment(comment: EventComment) -> dict[str, Any]:
    return {
        "id": comment.id,
        "event_id": str(comment.event_id),
        "author_id": str(comment.author_id),
        "author_name": comment.author.display_name,
        "body": comment.body,
        "created_at": comment.created_at,
    }


@router.get("/events/{event_id}/comments", response=list[CommentOut])
def list_comments(request: AuthedRequest, event_id: str) -> list[dict[str, Any]]:
    event, _ = get_visible_event(event_id, request.user)
    return [_serialize_comment(c) for c in EventComment.objects.filter(event=event).order_by("created_at")]


@router.post("/events/{event_id}/comments", response=CommentOut)
def create_comment(request: AuthedRequest, event_id: str, payload: CommentCreate) -> dict[str, Any]:
    event, membership = get_visible_event(event_id, request.user)
    if not has_at_least_role(membership, Role.OWN):
        raise HttpError(403, "You do not have permission to comment")
    return _serialize_comment(comments.add_comment(event, request.user, payload.body))


@router.delete("/events/{event_id}/comments/{comment_id}", response=OkOut)
def delete_comment(request: AuthedRequest, event_id: str, comment_id: str) -> dict[str, bool]:
    comment = EventComment.objects.get(id=comment_id, event_id=event_id)
    membership = get_membership(comment.event.calendar, request.user)
    may_moderate = membership is not None and has_at_least_role(membership, Role.FULL)
    if comment.author_id != request.user.id and not may_moderate:
        raise HttpError(403, "You do not have permission to delete this comment")
    comment.delete()
    return {"ok": True}


@router.get("/events/{event_id}/activity", response=list[ActivityOut])
def list_activity(request: AuthedRequest, event_id: str) -> list[ActivityOut]:
    event, _ = get_visible_event(event_id, request.user)
    entries = EventActivity.objects.filter(event=event).order_by("created_at")
    return [
        ActivityOut(
            id=str(e.id),
            event_id=str(e.event_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_name=e.actor.display_name if e.actor else None,
            action=e.action,
            details=e.details,
            created_at=e.created_at,
        )
        for e in entries
    ]
