"""
Base model helpers and shared enums.
"""

import uuid

import uuid_utils
from django.db import models


def new_uuid7() -> uuid.UUID:
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)


def as_uuid(value) -> uuid.UUID | None:
    """The UUID a string spells, or None: for values that may be an id or a name (a calendar's URL
    path, a CalDAV path segment), as looking up a UUID field with anything else fails."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


class UUIDModel(models.Model):
    """A model whose primary key is a UUIDv7, which sorts by creation time."""

    id = models.UUIDField(primary_key=True, default=new_uuid7, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """A model that remembers when it was created and last saved."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def default_weekend_days() -> list[int]:
    return [0, 6]

class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    # Everything the owner may, except deleting the calendar and changing its owner.
    MANAGE = "manage", "Manage"
    FULL = "full", "All events"
    OWN = "own", "Own events"
    READ = "read", "Read only"


class MembershipSource(models.TextChoices):
    """
    Where a membership comes from. Only direct ones are granted by hand and hold a role; the others the app
    makes and removes along with what they come from (core.services.memberships), their role is that source's.
    """

    # Granted to the user in the calendar's access settings (and the owner's own).
    DIRECT = "direct", "Direct"
    # The user is in a group the calendar is shared with; the best role of those groups applies.
    GROUP = "group", "Group"
    # A public calendar the user added to their sidebar; the calendar's public role applies.
    PUBLIC = "public", "Public"


class EventStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class ParticipantStatus(models.TextChoices):
    NEEDS_ACTION = "needs_action", "Needs action"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    TENTATIVE = "tentative", "Tentative"
