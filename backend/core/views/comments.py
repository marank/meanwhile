"""
Event comments and activity endpoints.
"""


from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import EventActivity, EventComment
from core.models.base import Role
from core.schemas import ActivityOut, CommentCreate, CommentOut
from core.services.notifications import notify
from core.services.permissions import get_membership, get_visible_event, has_at_least_role

router = CSRFRouter()


def _serialize_comment(comment: EventComment) -> dict:
    return {
        "id": comment.id,
        "event_id": str(comment.event_id),
        "author_id": str(comment.author_id),
        "author_name": comment.author.display_name if comment.author else "",
        "body": comment.body,
        "created_at": comment.created_at,
    }


@router.get("/events/{event_id}/comments", response=list[CommentOut], auth=django_auth)
def list_comments(request, event_id: str):
    event, _ = get_visible_event(event_id, request.user)
    comments = EventComment.objects.filter(event=event).order_by("created_at")
    return [_serialize_comment(c) for c in comments]


@router.post("/events/{event_id}/comments", response=CommentOut, auth=django_auth)
def create_comment(request, event_id: str, payload: CommentCreate):
    event, membership = get_visible_event(event_id, request.user)
    if not has_at_least_role(membership, Role.OWN):
        raise HttpError(403, "You do not have permission to comment")
    body = payload.body.strip()
    if not body:
        raise HttpError(422, "Comment must not be empty")
    comment = EventComment.objects.create(
        event=event,
        author=request.user,
        body=body,
    )
    previous_commenters = (
        EventComment.objects.filter(event=event)
        .values_list("author_id", flat=True)
        .distinct()
    )
    notify(
        [str(event.creator_id)] + [str(aid) for aid in previous_commenters],
        "comment_added",
        str(request.user.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"comment": body[:1000]},
    )
    return _serialize_comment(comment)


@router.delete("/events/{event_id}/comments/{comment_id}", auth=django_auth)
def delete_comment(request, event_id: str, comment_id: str):
    try:
        comment = EventComment.objects.get(id=comment_id, event_id=event_id)
    except EventComment.DoesNotExist:
        raise HttpError(404, "Comment not found")
    membership = get_membership(comment.event.calendar, request.user)
    if comment.author_id != request.user.id and not has_at_least_role(membership, Role.FULL):
        raise HttpError(403, "You do not have permission to delete this comment")
    comment.delete()
    return {"ok": True}


@router.get("/events/{event_id}/activity", response=list[ActivityOut], auth=django_auth)
def list_activity(request, event_id: str):
    event, _ = get_visible_event(event_id, request.user)
    entries = EventActivity.objects.filter(event=event).order_by("created_at")
    return [
        ActivityOut(
            id=e.id,
            event_id=str(e.event_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_name=e.actor.display_name if e.actor else None,
            action=e.action,
            details=e.details,
            created_at=e.created_at,
        )
        for e in entries
    ]
