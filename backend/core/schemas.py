"""
Request and response schemas of the API. Ninja's Schema reads attributes, so models can be returned as they are.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ninja import Field
from ninja import Schema as NinjaSchema
from pydantic import AfterValidator, BeforeValidator, ConfigDict, WithJsonSchema, model_validator

from core.models.base import EventStatus, ParticipantStatus, Role
from core.models.users import get_or_create_app_settings
from core.services.notifications import email_preferences
from core.services.recurrence import validate_rrule


class Schema(NinjaSchema):
    # The OpenAPI schema (and the frontend's types generated from it) marks response fields with a
    # default as always present, as they are; request fields with one stay optional.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


Weekday = Annotated[int, Field(ge=0, le=6)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


def _known_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        raise ValueError("Unknown time zone") from None
    return name


TimeZoneName = Annotated[str, AfterValidator(_known_zone)]

# Ids are UUIDs in the database and strings in the API; objects given to a response carry UUIDs.
Id = Annotated[
    str,
    BeforeValidator(lambda value: str(value) if isinstance(value, uuid.UUID) else value),
    WithJsonSchema({"type": "string", "format": "uuid"}),
]


def _single_address(value: str) -> str:
    # One plain address, as invitations are mailed to it: no names, lists or line breaks.
    try:
        validate_email(value)
    except ValidationError:
        raise ValueError("Not a valid email address") from None
    return value


EmailAddress = Annotated[str, Field(max_length=254), AfterValidator(_single_address)]
RRule = Annotated[str, AfterValidator(validate_rrule)]

# Text that clients may also send as null for "none"; it is stored as "".
Text = Annotated[
    str,
    BeforeValidator(lambda value: "" if value is None else value),
    WithJsonSchema({"anyOf": [{"type": "string"}, {"type": "null"}]}, mode="validation"),
]

TimeFormat = Literal["auto", "24h", "12h"]
DateFormat = Literal["auto", "dmy", "mdy", "ymd"]
# The roles a group or the public can be given; ownership is never granted.
GrantableRole = Literal["read", "own", "full", "manage"]
# Never "manage": managing the calendar is only for people it was granted to.
PublicRole = Literal["read", "own", "full"]
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


class OkOut(Schema):
    """The answer of endpoints that only do something, such as deleting."""

    ok: bool


# ---------------------------------------------------------------------------
# Auth & users
# ---------------------------------------------------------------------------


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
    reminders: bool


class EmailNotificationsUpdate(Schema):
    invitations: bool | None = None
    responses: bool | None = None
    approvals: bool | None = None
    decisions: bool | None = None
    comments: bool | None = None
    memberships: bool | None = None
    reminders: bool | None = None


class ProfileOut(UserOut):
    """The signed-in user, as /users/me and the login and signup answers (core.headless_adapter) show them."""

    email_notifications: EmailNotifications

    @staticmethod
    def resolve_email_notifications(obj):
        # What the user chose, completed with the defaults of the kinds they never chose.
        return email_preferences(obj)


class UserUpdate(Schema):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    time_format: TimeFormat | None = None
    date_format: DateFormat | None = None
    timezone: TimeZoneName | None = None
    language: Literal["en", "de"] | None = None
    email_notifications: EmailNotificationsUpdate | None = None


class WeekLayoutOut(Schema):
    """The week layout of a calendar or the overview; what isn't set there follows the app's defaults."""

    first_weekday: int
    show_weekends: bool
    weekend_days: list[Weekday]
    show_week_numbers: bool

    @staticmethod
    def resolve_first_weekday(obj, context):
        return _layout_value(obj, "first_weekday", context)

    @staticmethod
    def resolve_show_weekends(obj, context):
        return _layout_value(obj, "show_weekends", context)

    @staticmethod
    def resolve_weekend_days(obj, context):
        return _layout_value(obj, "weekend_days", context)

    @staticmethod
    def resolve_show_week_numbers(obj, context):
        return _layout_value(obj, "show_week_numbers", context)


def _layout_value(obj, field: str, context):
    value = obj[field] if isinstance(obj, dict) else getattr(obj, field)
    if value is not None:
        return value
    # Loaded once per request, however many calendars are listed.
    request = (context or {}).get("request")
    app_settings = getattr(request, "_app_settings", None)
    if app_settings is None:
        app_settings = get_or_create_app_settings()
        if request is not None:
            request._app_settings = app_settings
    return getattr(app_settings, f"default_{field}")


class OverviewSettingsOut(WeekLayoutOut):
    use_calendar_colors: bool
    base_color: str
    weekend_color: str
    today_color: str
    event_color: str
    border_color: str
    outer_border_color: str
    dark_base_color: str
    dark_weekend_color: str
    dark_today_color: str
    dark_event_color: str
    dark_border_color: str
    dark_outer_border_color: str


class OverviewSettingsUpdate(Schema):
    first_weekday: int | None = Field(None, ge=0, le=6)
    show_weekends: bool | None = None
    weekend_days: list[Weekday] | None = None
    show_week_numbers: bool | None = None
    use_calendar_colors: bool | None = None
    base_color: Color | None = None
    weekend_color: Color | None = None
    today_color: Color | None = None
    event_color: Color | None = None
    border_color: Color | None = None
    outer_border_color: Color | None = None
    dark_base_color: Color | None = None
    dark_weekend_color: Color | None = None
    dark_today_color: Color | None = None
    dark_event_color: Color | None = None
    dark_border_color: Color | None = None
    dark_outer_border_color: Color | None = None


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


class SearchResult(Schema):
    id: Id
    type: str
    label: str
    subtitle: str | None = None
    meta: dict | None = None


class GroupOut(Schema):
    id: Id
    name: str
    description: str = ""
    member_count: int = 0


class GroupMemberOut(Schema):
    id: Id
    email: str
    display_name: str


class GroupDetailOut(GroupOut):
    members: list[GroupMemberOut] = []


class GroupCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    member_ids: list[Id] = []


class GroupUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    # Replaces the member list when given.
    member_ids: list[Id] | None = None


class AdminUserOut(Schema):
    id: Id
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    groups: list[GroupOut] = []


class AdminUserCreate(Schema):
    email: str = Field(..., pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    is_admin: bool = False
    is_active: bool = True
    group_ids: list[Id] | None = None


class AdminUserUpdate(Schema):
    email: str | None = Field(None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=8)
    is_admin: bool | None = None
    is_active: bool | None = None
    group_ids: list[Id] | None = None


class AdminPasswordResetOut(Schema):
    password: str


class AppSettingsOut(Schema):
    id: int
    app_name: str
    logo_url: str = ""
    favicon_url: str = ""
    default_first_weekday: int
    default_show_weekends: bool
    default_weekend_days: list[int]
    default_show_week_numbers: bool


class AppSettingsUpdate(Schema):
    app_name: str | None = Field(None, min_length=1, max_length=255)
    logo_url: Text = Field("", max_length=1_000_000)
    favicon_url: Text = Field("", max_length=1_000_000)
    default_first_weekday: int | None = Field(None, ge=0, le=6)
    default_show_weekends: bool | None = None
    default_weekend_days: list[int] | None = None
    default_show_week_numbers: bool | None = None


# ---------------------------------------------------------------------------
# Calendar folders
# ---------------------------------------------------------------------------


class FolderCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Id | None = None
    position: int = 0


class FolderUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    parent_id: Id | None = None
    position: int | None = None


class FolderOut(Schema):
    id: Id
    name: str
    parent_id: Id | None
    position: int


# ---------------------------------------------------------------------------
# Calendar members
# ---------------------------------------------------------------------------


class CalendarMemberCreate(Schema):
    user_id: Id
    role: Role = Role.READ


class CalendarMemberUpdate(Schema):
    role: Role | None = None


class CalendarMemberBatchOut(Schema):
    id: Id
    calendar_id: Id
    user_id: Id
    role: Role
    folder_id: Id | None
    position: int


class CalendarMemberOut(CalendarMemberBatchOut):
    email: str
    display_name: str


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


class CalendarCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    force_all_day: bool = False
    first_weekday: int | None = Field(None, ge=0, le=6)
    show_weekends: bool | None = None
    weekend_days: list[Weekday] | None = None
    show_week_numbers: bool | None = None
    # Colors left out start with the default preset.
    base_color: Color | None = None
    weekend_color: Color | None = None
    today_color: Color | None = None
    event_color: Color | None = None
    border_color: Color | None = None
    outer_border_color: Color | None = None
    dark_base_color: Color | None = None
    dark_weekend_color: Color | None = None
    dark_today_color: Color | None = None
    dark_event_color: Color | None = None
    dark_border_color: Color | None = None
    dark_outer_border_color: Color | None = None


class CalendarUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    url_path: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    force_all_day: bool | None = None
    first_weekday: int | None = Field(None, ge=0, le=6)
    show_weekends: bool | None = None
    weekend_days: list[Weekday] | None = None
    show_week_numbers: bool | None = None
    base_color: Color | None = None
    weekend_color: Color | None = None
    today_color: Color | None = None
    event_color: Color | None = None
    border_color: Color | None = None
    outer_border_color: Color | None = None
    dark_base_color: Color | None = None
    dark_weekend_color: Color | None = None
    dark_today_color: Color | None = None
    dark_event_color: Color | None = None
    dark_border_color: Color | None = None
    dark_outer_border_color: Color | None = None
    is_public: bool | None = None
    public_role: PublicRole | None = None


class CalendarOut(WeekLayoutOut):
    id: Id
    name: str
    description: str = ""
    url_path: str | None
    force_all_day: bool
    base_color: str
    weekend_color: str
    today_color: str
    event_color: str
    border_color: str
    outer_border_color: str
    dark_base_color: str
    dark_weekend_color: str
    dark_today_color: str
    dark_event_color: str
    dark_border_color: str
    dark_outer_border_color: str
    is_public: bool
    public_role: PublicRole
    owner_id: Id
    created_at: datetime
    updated_at: datetime
    my_membership: CalendarMemberOut | None = None


class CalendarListOut(Schema):
    calendar: CalendarOut
    membership: CalendarMemberOut
    # Where the access comes from: a membership, a group, or a public calendar added to the sidebar.
    access: Literal["member", "group", "public"]


class PublicCalendarOut(Schema):
    """A public calendar to add to the sidebar."""

    id: Id
    name: str
    description: str = ""
    owner_name: str
    added: bool


# ---------------------------------------------------------------------------
# Calendar group links
# ---------------------------------------------------------------------------


class CalendarGroupLinkGroupInfo(Schema):
    id: Id
    name: str


class CalendarGroupLinkMember(Schema):
    id: Id
    email: str
    display_name: str


class CalendarGroupLinkOut(Schema):
    id: Id
    group: CalendarGroupLinkGroupInfo
    role: GrantableRole
    # Everyone in the group, who therefore has the role in this calendar.
    members: list[CalendarGroupLinkMember]


class CalendarGroupLinkCreate(Schema):
    group_id: Id
    role: GrantableRole = "read"


class CalendarGroupLinkUpdate(Schema):
    role: GrantableRole | None = None


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ApproversIn(Schema):
    """The complete list of approvers; whoever is not in it is no approver any more."""

    user_ids: list[Id]


class ApproverOut(Schema):
    user_id: Id
    email: str
    display_name: str


# An icon's name: lower-case words joined by hyphens, or empty for none. Which names exist is up to the client.
ResourceIconName = Annotated[str, Field(max_length=40, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$|^$")]


class ResourceCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    color: Color = "#f59e0b"
    icon: ResourceIconName = ""
    requires_approval: bool = False
    is_location: bool = False
    is_active: bool = True


class ResourceUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    color: Color | None = None
    icon: ResourceIconName | None = None
    requires_approval: bool | None = None
    is_location: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def refuse_nulls(self) -> ResourceUpdate:
        # A field left out keeps its value; null would empty a column that can't be empty.
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"May not be null: {', '.join(nulls)}")
        return self


class ResourceOut(Schema):
    id: Id
    calendar_id: Id
    name: str
    description: str = ""
    color: str
    icon: str
    requires_approval: bool
    is_location: bool
    is_active: bool
    approvers: list[ApproverOut]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_approvers(obj):
        # The related ResourceApprover rows only carry the user, not its email or name.
        return [
            ApproverOut(user_id=a.user_id, email=a.user.email, display_name=a.user.display_name)
            for a in obj.approvers.all()
        ]


class CategoryCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    color: str = "#64748b"


class CategoryUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    color: str | None = None


class CategoryOut(Schema):
    id: Id
    calendar_id: Id
    name: str
    description: str = ""
    color: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventParticipantInvite(Schema):
    user_id: Id | None = None
    email: EmailAddress | None = None
    status: ParticipantStatus | None = ParticipantStatus.NEEDS_ACTION

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> EventParticipantInvite:
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
    participants: list[EventParticipantInvite] | None = None


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


class EventParticipantCreate(Schema):
    user_id: Id | None = None
    email: EmailAddress | None = None
    status: ParticipantStatus | None = ParticipantStatus.NEEDS_ACTION

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> EventParticipantCreate:
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        return self


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
    details: dict | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(Schema):
    id: Id
    type: NotificationType
    actor_id: Id | None
    actor_name: str | None
    calendar_id: Id | None
    event_id: Id | None
    title: str
    data: dict | None
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


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalAction(Schema):
    note: Text = ""


class ApprovalOut(EventOut):
    approver_pool: list[ApproverOut]


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


class FeedUrlOut(Schema):
    feed_url: str


class FeedTokenRotateOut(Schema):
    feed_url: str


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


class LayoutItem(Schema):
    id: Id
    type: Literal["calendar", "folder"]
    position: int
    parent_id: Id | None = None


class LayoutItemsUpdate(Schema):
    items: list[LayoutItem]


class LayoutOut(Schema):
    folders: list[FolderOut]
    calendars: list[CalendarListOut]


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


class BookingConflict(Schema):
    message: str = "Resource booking conflict"
    conflicts: list[dict]


class AvailabilityIn(Schema):
    """A query, sent as a body: the lists of ids would make for long URLs (and land in access logs)."""

    start: datetime
    end: datetime
    user_ids: list[Id] = []
    resource_ids: list[Id] = []
    # An event being edited doesn't count as taking its own time.
    exclude_event_id: Id | None = None


class BusyPeriod(Schema):
    start: datetime
    end: datetime
    # Pending bookings and invitations not answered yet.
    tentative: bool


class AvailabilityEntry(Schema):
    id: Id
    name: str
    busy: list[BusyPeriod]


class AvailabilityOut(Schema):
    users: list[AvailabilityEntry]
    resources: list[AvailabilityEntry]


# ---------------------------------------------------------------------------
# Answering invitations by link (no account needed)
# ---------------------------------------------------------------------------


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
