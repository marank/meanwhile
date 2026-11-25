"""
Notification endpoints.
"""

from collections.abc import Iterable
from typing import Any, Literal
from uuid import UUID

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext
from ninja import Router
from ninja.errors import HttpError

from apps.core.models import EventParticipant, Notification, User
from apps.core.models.base import EventStatus, ParticipantStatus
from apps.core.schemas import NotificationCountsOut, NotificationOut, OkOut
from apps.core.services.notifications import mark_all_read as mark_all_notifications_read
from apps.core.services.notifications import notification_link
from apps.core.views.common import AuthedRequest

router = Router()

APPROVAL_TYPES = {"approval_requested", "booking_approved", "booking_rejected", "booking_cancelled"}
INVITATION_TYPES = {"participant_added"}
# Requests that still need an answer must stay reachable, so they can't be deleted.
UNDELETABLE_TYPES = {"approval_requested", "participant_added"}
TYPE_GROUPS = {"approvals": APPROVAL_TYPES, "invitations": INVITATION_TYPES}


def _my_responses(user: User, notifications: Iterable[Notification]) -> dict[UUID, str]:
    event_ids = {n.event_id for n in notifications if n.type in INVITATION_TYPES and n.event_id}
    if not event_ids:
        return {}
    return dict(
        EventParticipant.objects.filter(event_id__in=event_ids)
        .filter(Q(user=user) | Q(email__iexact=user.email))
        .values_list("event_id", "status")
    )


def _serialize(notification: Notification, responses: dict[UUID, str] | None = None) -> dict[str, Any]:
    event = notification.event
    user = notification.user
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
        "response_status": responses.get(notification.event_id) if responses and notification.event_id else None,
        "deletable": notification.type not in UNDELETABLE_TYPES,
        "link": notification_link(user, notification.type, event, notification.calendar_id),
    }


MAX_NOTIFICATIONS = 200


@router.get("/notifications", response=list[NotificationOut])
def list_notifications(
    request: AuthedRequest, limit: int = 50, group: Literal["approvals", "invitations"] | None = None
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, MAX_NOTIFICATIONS))
    query = Notification.objects.filter(user=request.user)
    if group is not None:
        query = query.filter(type__in=TYPE_GROUPS[group])
    notifications = list(query.select_related("actor", "event__calendar", "user").order_by("-created_at")[:limit])
    responses = _my_responses(request.user, notifications)
    return [_serialize(n, responses) for n in notifications]


@router.get("/notifications/counts", response=NotificationCountsOut)
def counts(request: AuthedRequest) -> dict[str, int]:
    """The numbers the app shows as badges: unread notifications, and requests still waiting for this user
    (pending approvals and unanswered invitations)."""
    unread = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    approvals = (
        Notification.objects.filter(user=request.user, type="approval_requested", event__status=EventStatus.PENDING)
        .values("event_id")
        .distinct()
        .count()
    )
    invitations = (
        EventParticipant.objects.filter(status=ParticipantStatus.NEEDS_ACTION)
        .filter(Q(user=request.user) | Q(email__iexact=request.user.email))
        .exclude(event__creator=request.user)
        .count()
    )
    return {"unread": unread, "approvals": approvals, "invitations": invitations}


@router.post("/notifications/read-all", response=OkOut)
def mark_all_read(request: AuthedRequest) -> dict[str, bool]:
    mark_all_notifications_read(request.user)
    return {"ok": True}


@router.post("/notifications/{notification_id}/read", response=NotificationOut)
def mark_read(request: AuthedRequest, notification_id: str) -> dict[str, Any]:
    notification = Notification.objects.get(id=notification_id, user=request.user)
    notification.read_at = timezone.now()
    notification.save()
    return _serialize(notification)


@router.delete("/notifications/{notification_id}", response=OkOut)
def delete_notification(request: AuthedRequest, notification_id: str) -> dict[str, bool]:
    notification = Notification.objects.get(id=notification_id, user=request.user)
    if notification.type in UNDELETABLE_TYPES:
        raise HttpError(400, gettext("This notification cannot be deleted"))
    notification.delete()
    return {"ok": True}
