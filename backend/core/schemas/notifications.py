"""
Notifications.
"""

from datetime import datetime
from typing import Any, Literal

from core.models.base import EventStatus, ParticipantStatus
from core.schemas.common import Id, Schema

NotificationType = Literal[
    "approval_requested",
    "booking_approved",
    "booking_rejected",
    "booking_cancelled",
    "participant_added",
    "member_added",
    "member_role_changed",
    "comment_added",
    "event_reminder",
    "participant_replied",
]


class NotificationOut(Schema):
    id: Id
    type: NotificationType
    actor_id: Id | None
    actor_name: str | None
    calendar_id: Id | None
    event_id: Id | None
    title: str
    data: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime
    # Current status of the linked event and, for invitations, the user's own answer.
    event_status: EventStatus | None = None
    response_status: ParticipantStatus | None = None
    deletable: bool = True


class NotificationCountsOut(Schema):
    unread: int
    # Pending bookings this user may decide, and invitations they haven't answered.
    approvals: int
    invitations: int


class NotificationUpdate(Schema):
    read: bool
