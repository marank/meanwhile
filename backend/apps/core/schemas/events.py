"""
Events, their participants, occurrences, comments, activity and approvals.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from ninja import Field
from pydantic import AfterValidator, model_validator

from apps.core.models.base import AttachmentKind, EventStatus, ParticipantStatus, ShowAs
from apps.core.schemas.common import EmailAddress, Id, RRule, Schema, Text, TimeZoneName
from apps.core.schemas.resources import ApproverOut

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventParticipantCreate(Schema):
    user_id: Id | None = None
    email: EmailAddress | None = None
    status: ParticipantStatus | None = ParticipantStatus.NEEDS_ACTION

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> EventParticipantCreate:
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        return self


class EventCreate(Schema):
    title: str | None = Field(default=None, max_length=255)
    description: Text = ""
    location: str | None = Field(default=None, max_length=255)
    # A resource marked as location to book; the location then is its name.
    location_resource_id: Id | None = None
    start: datetime
    end: datetime
    all_day: bool = False
    timezone: TimeZoneName | None = None
    show_recurrence_count: bool = False
    rrule: RRule | None = None
    category_id: Id | None = None
    resource_id: Id | None = None
    show_as: ShowAs = ShowAs.BUSY
    participants: list[EventParticipantCreate] | None = None


class EventUpdate(Schema):
    title: str | None = Field(None, max_length=255)
    description: Text = ""
    location: str | None = Field(None, max_length=255)
    location_resource_id: Id | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool | None = None
    timezone: TimeZoneName | None = None
    show_recurrence_count: bool | None = None
    rrule: RRule | None = None
    category_id: Id | None = None
    resource_id: Id | None = None
    show_as: ShowAs | None = None


class EventRemindersIn(Schema):
    # Minutes before each occurrence's start; 0 is at the start.
    minutes: list[int]


class EventRemindersOut(Schema):
    minutes: list[int]


class EventParticipantUpdate(Schema):
    status: ParticipantStatus


class EventParticipantOut(Schema):
    id: Id
    event_id: Id
    user_id: Id | None
    email: str
    display_name: str | None
    status: ParticipantStatus
    created_at: datetime
    updated_at: datetime


class EventOut(Schema):
    id: Id
    calendar_id: Id
    creator_id: Id
    creator_name: str | None = None
    creator_email: str | None = None
    title: str
    description: str = ""
    location: str = ""
    location_resource_id: Id | None = None
    location_resource_name: str | None = None
    start: datetime
    end: datetime
    all_day: bool
    timezone: str
    show_recurrence_count: bool
    rrule: str | None
    # Extra occurrence starts besides those of the rule (RDATE), e.g. from other clients.
    rdates: list[datetime] = []
    uid: str
    # Set when the event is a changed occurrence of the series parent_id.
    parent_id: Id | None = None
    recurrence_id: datetime | None = None
    category_id: Id | None
    category_name: str | None
    category_color: str | None
    resource_id: Id | None
    resource_name: str | None
    status: EventStatus
    show_as: ShowAs
    # Names of the booked resources a pending event still waits to have approved.
    awaiting_approval: list[str] = []
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str = ""
    created_at: datetime
    updated_at: datetime
    # Whether the current user may approve or reject this pending booking.
    can_decide: bool = False


OccurrenceScope = Literal["this", "following", "all"]


class OccurrenceOut(Schema):
    event_id: Id
    # Clients take the event colors from the calendar, so they follow color changes right away.
    calendar_id: Id
    title: str
    description: str = ""
    start: datetime
    end: datetime
    all_day: bool
    recurrence_count: int | None
    status: EventStatus
    show_as: ShowAs
    category_id: Id | None
    category_name: str | None
    category_color: str | None
    resource_id: Id | None
    resource_name: str | None
    resource_icon: str = ""
    location: str = ""
    location_resource_id: Id | None = None
    location_resource_icon: str = ""
    creator_id: Id
    can_edit: bool
    is_recurring: bool
    # For occurrences of a series: the series and the occurrence's original start, which
    # identify it in /events/{series_id}/occurrences/{recurrence_id}.
    series_id: Id | None = None
    recurrence_id: datetime | None = None


class EventDuplicate(Schema):
    """Where a copy of an event goes: its calendar and start (it lasts as long as the original)."""

    calendar_id: Id
    start: datetime
    # Invites the original's participants to the copy (they're sent invitations).
    invite_participants: bool = False


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


def _web_address(value: str) -> str:
    # Other schemes (javascript:, file:, data:) aren't links one should be sent to.
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("Only http and https links can be attached")
    return value.strip()


WebAddress = Annotated[str, Field(max_length=2000), AfterValidator(_web_address)]


class AttachmentLinkCreate(Schema):
    url: WebAddress
    # Shown instead of the address; the address when empty.
    name: str = Field(default="", max_length=255)


class AttachmentOut(Schema):
    id: Id
    kind: AttachmentKind
    name: str
    # Where it is opened: a link's address, or where a file is downloaded.
    url: str
    # A file's type and size in bytes; empty and 0 for links.
    content_type: str
    size: int
    added_by_name: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Event comments & activity
# ---------------------------------------------------------------------------


class CommentCreate(Schema):
    body: str = Field(..., min_length=1, max_length=5000)


class CommentOut(Schema):
    id: Id
    event_id: Id
    author_id: Id
    author_name: str
    body: str
    created_at: datetime


class ActivityOut(Schema):
    id: Id
    event_id: Id
    actor_id: Id | None
    actor_name: str | None
    action: str
    details: dict[str, Any] | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalAction(Schema):
    note: Text = ""


class ApprovalOut(EventOut):
    approver_pool: list[ApproverOut]
