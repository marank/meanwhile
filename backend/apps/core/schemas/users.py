"""
The signed-in user: profile, preferences and app passwords.
"""

from datetime import datetime
from typing import Literal

from ninja import Field

from apps.core.models.users import User
from apps.core.schemas.common import DateFormat, Id, Schema, TimeFormat, TimeZoneName
from apps.core.services.notifications import email_preferences


class UserOut(Schema):
    id: Id
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    time_format: TimeFormat
    date_format: DateFormat
    # IANA zone of the user's browser; empty until the app reported it.
    timezone: str = ""
    # Language of the app, for emails; empty until the app reported it.
    language: str = ""
    created_at: datetime


class EmailNotifications(Schema):
    """Which kinds of notifications also come by email."""

    invitations: bool
    responses: bool
    approvals: bool
    decisions: bool
    comments: bool
    memberships: bool
    role_changes: bool
    reminders: bool


class EmailNotificationsUpdate(Schema):
    invitations: bool | None = None
    responses: bool | None = None
    approvals: bool | None = None
    decisions: bool | None = None
    comments: bool | None = None
    memberships: bool | None = None
    role_changes: bool | None = None
    reminders: bool | None = None


# The kinds of email users can switch off (apps.core.services.notifications.EMAIL_KINDS).
EmailKind = Literal[
    "invitations", "responses", "approvals", "decisions", "comments", "memberships", "role_changes", "reminders"
]


class UnsubscribeOut(Schema):
    """What an unsubscribe link in an email's footer is about: whose emails of which kind, or about
    which event (`event_title`, and no kind)."""

    email: str
    kind: EmailKind | None
    event_title: str | None
    # Whether these emails still come.
    subscribed: bool


class ProfileOut(UserOut):
    """The signed-in user, as /users/me and the login and signup answers (apps.core.headless_adapter) show them."""

    email_notifications: EmailNotifications
    day_start: int

    @staticmethod
    def resolve_email_notifications(obj: User) -> dict[str, bool]:
        # What the user chose, completed with the defaults of the kinds they never chose.
        return email_preferences(obj)


class UserUpdate(Schema):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    time_format: TimeFormat | None = None
    date_format: DateFormat | None = None
    timezone: TimeZoneName | None = None
    language: Literal["en", "de", "de-informal"] | None = None
    day_start: int | None = Field(None, ge=0, le=23)
    email_notifications: EmailNotificationsUpdate | None = None


class AppPasswordCreate(Schema):
    label: str = Field(..., min_length=1, max_length=255)


class AppPasswordOut(Schema):
    id: Id
    label: str
    last_used_at: datetime | None = None
    created_at: datetime


class AppPasswordCreated(Schema):
    id: Id
    label: str
    password: str
