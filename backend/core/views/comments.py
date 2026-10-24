"""
Event comments and activity endpoints.
"""


from ninja import Router
from ninja.errors import HttpError

from core.models import EventActivity, EventComment, User
from core.models.base import Role
from core.schemas import ActivityOut, CommentCreate, CommentOut
from core.services.notifications import notify
from core.services.permissions import can_see_event, get_membership, get_visible_event, has_at_least_role

router = Router()


def _serialize_comment(comment: EventComment) -> dict:
    return {
        "id": comment.id,
        "event_id": str(comment.event_id),
        "author_id": str(comment.author_id),
        "author_name": comment.author.display_name if comment.author else "",
        "body": comment.body,
        "created_at": comment.created_at,
    }


@router.get("/events/{event_id}/comments", response=list[CommentOut])
def list_comments(request, event_id: str):
    event, _ = get_visible_event(event_id, request.user)
    comments = EventComment.objects.filter(event=event).order_by("created_at")
    return [_serialize_comment(c) for c in comments]


@router.post("/events/{event_id}/comments", response=CommentOut)
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
    # Only who may still see the event: the notification carries the comment.
    recipients = [
        user
        for user in User.objects.filter(id__in={event.creator_id, *previous_commenters}, is_active=True)
        if (access := get_membership(event.calendar, user)) is not None and can_see_event(event, user, access)
    ]
    notify(
        [str(user.id) for user in recipients],
        "comment_added",
        str(request.user.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"comment": body[:1000]},
    )
    return _serialize_comment(comment)


@router.delete("/events/{event_id}/comments/{comment_id}")
def delete_comment(request, event_id: str, comment_id: str):
    comment = EventComment.objects.get(id=comment_id, event_id=event_id)
    membership = get_membership(comment.event.calendar, request.user)
    may_moderate = membership is not None and has_at_least_role(membership, Role.FULL)
    if comment.author_id != request.user.id and not may_moderate:
        raise HttpError(403, "You do not have permission to delete this comment")
    comment.delete()
    return {"ok": True}


@router.get("/events/{event_id}/activity", response=list[ActivityOut])
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
