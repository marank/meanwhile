"""
Notification endpoints.
"""

from datetime import datetime, timezone

from ninja.errors import HttpError
from ninja.security import django_auth

from core.api import CSRFRouter
from django.db.models import Q

from core.models import EventParticipant, Notification
from core.models.base import EventStatus
from core.realtime import broadcast
from core.schemas import NotificationOut

router = CSRFRouter()

APPROVAL_TYPES = {"approval_requested", "booking_approved", "booking_rejected", "booking_cancelled"}
INVITATION_TYPES = {"participant_added"}
# Requests that still need an answer must stay reachable, so they can't be deleted.
UNDELETABLE_TYPES = {"approval_requested", "participant_added"}
TYPE_GROUPS = {"approvals": APPROVAL_TYPES, "invitations": INVITATION_TYPES}


def _my_responses(user, notifications) -> dict[str, str]:
    event_ids = {n.event_id for n in notifications if n.type in INVITATION_TYPES and n.event_id}
    if not event_ids:
        return {}
    return dict(
        EventParticipant.objects.filter(event_id__in=event_ids)
        .filter(Q(user=user) | Q(email__iexact=user.email))
        .values_list("event_id", "status")
    )


def _serialize(notification: Notification, responses: dict[str, str] | None = None) -> dict:
    event = notification.event
    return {
        "id": notification.id,
        "type": notification.type,
        "actor_id": str(notification.actor_id) if notification.actor_id else None,
        "actor_name": notification.actor.display_name if notification.actor else None,
        "calendar_id": str(notification.calendar_id) if notification.calendar_id else None,
        "event_id": str(notification.event_id) if notification.event_id else None,
        "title": notification.title,
        "data": notification.data,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
        "event_status": event.status if event else None,
        "response_status": (responses or {}).get(notification.event_id),
        "deletable": notification.type not in UNDELETABLE_TYPES,
    }


@router.get("/notifications", response=list[NotificationOut], auth=django_auth)
def list_notifications(request, limit: int = 50, group: str | None = None):
    query = Notification.objects.filter(user=request.user)
    if group is not None:
        if group not in TYPE_GROUPS:
            raise HttpError(422, "Unknown notification group")
        query = query.filter(type__in=TYPE_GROUPS[group])
    notifications = list(query.select_related("actor", "event").order_by("-created_at")[:limit])
    responses = _my_responses(request.user, notifications)
    return [_serialize(n, responses) for n in notifications]


@router.get("/notifications/counts", auth=django_auth)
def counts(request):
    """The numbers the app shows as badges: unread notifications, and requests still waiting for this user
    (pending approvals and unanswered invitations)."""
    unread = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    approvals = (
        Notification.objects.filter(
            user=request.user, type="approval_requested", event__status=EventStatus.PENDING
        )
        .values("event_id")
        .distinct()
        .count()
    )
    invitations = (
        EventParticipant.objects.filter(status="needs_action")
        .filter(Q(user=request.user) | Q(email__iexact=request.user.email))
        .exclude(event__creator=request.user)
        .count()
    )
    return {"unread": unread, "approvals": approvals, "invitations": invitations}


@router.post("/notifications/read-all", auth=django_auth)
def mark_all_read(request):
    now = datetime.now(timezone.utc)
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=now)
    # The bulk update sends no signal; the user's other tabs update their count.
    broadcast.notifications_changed(request.user.id)
    return {"ok": True}


@router.post("/notifications/{notification_id}/read", response=NotificationOut, auth=django_auth)
def mark_read(request, notification_id: str):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        raise HttpError(404, "Notification not found")
    notification.read_at = datetime.now(timezone.utc)
    notification.save()
    return _serialize(notification)


@router.delete("/notifications/{notification_id}", auth=django_auth)
def delete_notification(request, notification_id: str):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        raise HttpError(404, "Notification not found")
    if notification.type in UNDELETABLE_TYPES:
        raise HttpError(400, "This notification cannot be deleted")
    notification.delete()
    return {"ok": True}
