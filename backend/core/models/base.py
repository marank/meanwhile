"""
Base model helpers and shared enums.
"""

import uuid_utils


def new_uuid7() -> str:
    return str(uuid_utils.uuid7())


def default_weekend_days() -> list[int]:
    return [0, 6]


class Role:
    OWNER = "owner"
    # Everything the owner may, except deleting the calendar and changing its owner.
    MANAGE = "manage"
    FULL = "full"
    OWN = "own"
    READ = "read"

    CHOICES = [
        (OWNER, "Owner"),
        (MANAGE, "Manage"),
        (FULL, "All events"),
        (OWN, "Own events"),
        (READ, "Read only"),
    ]


class EventStatus:
    CONFIRMED = "confirmed"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    CHOICES = [
        (CONFIRMED, "Confirmed"),
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (CANCELLED, "Cancelled"),
    ]


class ParticipantStatus:
    NEEDS_ACTION = "needs_action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"

    CHOICES = [
        (NEEDS_ACTION, "Needs action"),
        (ACCEPTED, "Accepted"),
        (DECLINED, "Declined"),
        (TENTATIVE, "Tentative"),
    ]
