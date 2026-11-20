"""
Answering invitations by link (no account needed).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from apps.core.models.base import ParticipantStatus
from apps.core.schemas.common import Schema


class RsvpParticipantOut(Schema):
    # Anyone with the link sees this page, so others appear by their display name only, never by address:
    # null for guests and accounts without a name. The participant the link belongs to sees their own address.
    name: str | None
    status: ParticipantStatus
    # The one the link belongs to.
    you: bool


class RsvpOut(Schema):
    title: str
    start: datetime
    end: datetime
    all_day: bool
    timezone: str
    location: str
    description: str = ""
    rrule: str | None = None
    # Empty when the organizer has no display name (their address isn't shown here).
    organizer_name: str
    email: str
    status: ParticipantStatus
    # Cancelled or rejected: there is nothing to answer any more.
    cancelled: bool
    participants: list[RsvpParticipantOut]
    # The invitation is the signed-in user's own: the page is shown inside the app.
    yours: bool = False
    # Theirs and visible to them in the app: the page leads there instead.
    event_id: UUID | None = None


class RsvpAnswer(Schema):
    status: Literal["accepted", "tentative", "declined"]
