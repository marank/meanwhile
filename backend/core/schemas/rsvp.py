"""
Answering invitations by link (no account needed).
"""

from datetime import datetime
from typing import Literal

from core.models.base import ParticipantStatus
from core.schemas.common import Schema


class RsvpOut(Schema):
    title: str
    start: datetime
    end: datetime
    all_day: bool
    timezone: str
    location: str
    description: str = ""
    rrule: str | None = None
    organizer_name: str
    email: str
    status: ParticipantStatus
    # Cancelled or rejected: there is nothing to answer any more.
    cancelled: bool


class RsvpAnswer(Schema):
    status: Literal["accepted", "tentative", "declined"]
