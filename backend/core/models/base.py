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
    EDITOR = "editor"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"

    CHOICES = [
        (OWNER, "Owner"),
        (EDITOR, "Editor"),
        (CONTRIBUTOR, "Contributor"),
        (VIEWER, "Viewer"),
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
