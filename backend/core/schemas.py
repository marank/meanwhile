"""
Request and response schemas of the API. Ninja's Schema reads attributes, so models can be returned as they are.
"""

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ninja import Field, Schema
from pydantic import AfterValidator, BeforeValidator, model_validator

from core.models.base import ParticipantStatus, Role
from core.models.users import get_or_create_app_settings
from core.services.recurrence import validate_rrule

Weekday = Annotated[int, Field(ge=0, le=6)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


def _known_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown time zone") from None
    return name


TimeZoneName = Annotated[str, AfterValidator(_known_zone)]


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
Text = Annotated[str, BeforeValidator(lambda value: "" if value is None else value)]


# ---------------------------------------------------------------------------
# Auth & users
# ---------------------------------------------------------------------------


class UserOut(Schema):
    id: str
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    time_format: str
    date_format: str
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
    email_notifications: EmailNotifications


class UserUpdate(Schema):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    time_format: Literal["auto", "24h", "12h"] | None = None
    date_format: Literal["auto", "dmy", "mdy", "ymd"] | None = None
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
    id: str
    label: str
    last_used_at: datetime | None = None
    created_at: datetime


class AppPasswordCreated(Schema):
    id: str
    label: str
    password: str


class SearchResult(Schema):
    id: str
    type: str
    label: str
    subtitle: str | None = None
    meta: dict | None = None


class GroupOut(Schema):
    id: str
    name: str
    description: str = ""
    member_count: int = 0


class GroupMemberOut(Schema):
    id: str
    email: str
    display_name: str


class GroupDetailOut(GroupOut):
    members: list[GroupMemberOut] = []


class GroupCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    member_ids: list[str] = []


class GroupUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    # Replaces the member list when given.
    member_ids: list[str] | None = None


class AdminUserOut(Schema):
    id: str
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
    group_ids: list[str] | None = None


class AdminUserUpdate(Schema):
    email: str | None = Field(None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=8)
    is_admin: bool | None = None
    is_active: bool | None = None
    group_ids: list[str] | None = None


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
    parent_id: str | None = None
    position: int = 0


class FolderUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    parent_id: str | None = None
    position: int | None = None


class FolderOut(Schema):
    id: str
    name: str
    parent_id: str | None
    position: int


# ---------------------------------------------------------------------------
# Calendar members
# ---------------------------------------------------------------------------


class CalendarMemberCreate(Schema):
    user_id: str
    role: Role = Role.READ


class CalendarMemberUpdate(Schema):
    role: Role | None = None


class CalendarMemberBatchOut(Schema):
    id: str
    calendar_id: str
    user_id: str
    role: str
    folder_id: str | None
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
    # Never "manage": managing the calendar is only for people it was granted to.
    public_role: Literal["read", "own", "full"] | None = None


class CalendarOut(WeekLayoutOut):
    id: str
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
    public_role: str
    owner_id: str
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

    id: str
    name: str
    description: str = ""
    owner_name: str
    added: bool


# ---------------------------------------------------------------------------
# Calendar group links
# ---------------------------------------------------------------------------


class CalendarGroupLinkGroupInfo(Schema):
    id: str
    name: str


class CalendarGroupLinkMember(Schema):
    id: str
    email: str
    display_name: str


class CalendarGroupLinkOut(Schema):
    id: str
    group: CalendarGroupLinkGroupInfo
    role: str
    # Everyone in the group, who therefore has the role in this calendar.
    members: list[CalendarGroupLinkMember]


class CalendarGroupLinkCreate(Schema):
    group_id: str
    role: Literal["read", "own", "full", "manage"] = "read"


class CalendarGroupLinkUpdate(Schema):
    role: Literal["read", "own", "full", "manage"] | None = None


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ApproversIn(Schema):
    """The complete list of approvers; whoever is not in it is no approver any more."""

    user_ids: list[str]


class ApproverOut(Schema):
    user_id: str
    email: str
    display_name: str


# An icon's name: lower-case words joined by hyphens, or empty for none. Which names exist is up to the client.
ResourceIconName = Annotated[str, Field(max_length=40, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$|^$")]


class ResourceCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    color: str | None = "#f59e0b"
    icon: ResourceIconName = ""
    requires_approval: bool = False
    is_location: bool = False
    is_active: bool = True


class ResourceUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    color: str | None = None
    icon: ResourceIconName | None = None
    requires_approval: bool | None = None
    is_location: bool | None = None
    is_active: bool | None = None


class ResourceOut(Schema):
    id: str
    calendar_id: str
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
    id: str
    calendar_id: str
    name: str
    description: str = ""
    color: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventParticipantInvite(Schema):
    user_id: str | None = None
    email: EmailAddress | None = None
    status: ParticipantStatus | None = ParticipantStatus.NEEDS_ACTION

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> "EventParticipantInvite":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        return self


class EventCreate(Schema):
    title: str | None = Field(default=None, max_length=255)
    description: Text = ""
    location: str | None = Field(default=None, max_length=255)
    # A resource marked as location to book; the location then is its name.
    location_resource_id: str | None = None
    start: datetime
    end: datetime
    all_day: bool = False
    timezone: TimeZoneName | None = None
    show_recurrence_count: bool = False
    rrule: RRule | None = None
    category_id: str | None = None
    resource_id: str | None = None
    participants: list[EventParticipantInvite] | None = None


class EventUpdate(Schema):
    title: str | None = Field(None, max_length=255)
    description: Text = ""
    location: str | None = Field(None, max_length=255)
    location_resource_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool | None = None
    timezone: TimeZoneName | None = None
    show_recurrence_count: bool | None = None
    rrule: RRule | None = None
    category_id: str | None = None
    resource_id: str | None = None


class EventParticipantCreate(Schema):
    user_id: str | None = None
    email: EmailAddress | None = None
    status: ParticipantStatus | None = ParticipantStatus.NEEDS_ACTION

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> "EventParticipantCreate":
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
    id: str
    event_id: str
    user_id: str | None
    email: str
    display_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class EventOut(Schema):
    id: str
    calendar_id: str
    creator_id: str
    creator_name: str | None = None
    creator_email: str | None = None
    title: str
    description: str = ""
    location: str = ""
    location_resource_id: str | None = None
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
    parent_id: str | None = None
    recurrence_id: datetime | None = None
    category_id: str | None
    category_name: str | None
    category_color: str | None
    resource_id: str | None
    resource_name: str | None
    status: str
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
    event_id: str
    # Clients take the event colors from the calendar, so they follow color changes right away.
    calendar_id: str
    title: str
    description: str = ""
    start: datetime
    end: datetime
    all_day: bool
    recurrence_count: int | None
    status: str
    category_id: str | None
    category_name: str | None
    category_color: str | None
    resource_id: str | None
    resource_name: str | None
    resource_icon: str = ""
    location: str = ""
    location_resource_id: str | None = None
    location_resource_icon: str = ""
    creator_id: str
    can_edit: bool
    is_recurring: bool
    # For occurrences of a series: the series and the occurrence's original start, which
    # identify it in /events/{series_id}/occurrences/{recurrence_id}.
    series_id: str | None = None
    recurrence_id: datetime | None = None


# ---------------------------------------------------------------------------
# Event comments & activity
# ---------------------------------------------------------------------------


class CommentCreate(Schema):
    body: str = Field(..., min_length=1, max_length=5000)


class CommentOut(Schema):
    id: str
    event_id: str
    author_id: str
    author_name: str
    body: str
    created_at: datetime


class ActivityOut(Schema):
    id: str
    event_id: str
    actor_id: str | None
    actor_name: str | None
    action: str
    details: dict | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(Schema):
    id: str
    type: str
    actor_id: str | None
    actor_name: str | None
    calendar_id: str | None
    event_id: str | None
    title: str
    data: dict | None
    read_at: datetime | None
    created_at: datetime
    # Current status of the linked event and, for invitations, the user's own answer.
    event_status: str | None = None
    response_status: str | None = None
    deletable: bool = True


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
    id: str
    type: Literal["calendar", "folder"]
    position: int
    parent_id: str | None = None


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
    user_ids: list[str] = []
    resource_ids: list[str] = []
    # An event being edited doesn't count as taking its own time.
    exclude_event_id: str | None = None


class BusyPeriod(Schema):
    start: datetime
    end: datetime
    # Pending bookings and invitations not answered yet.
    tentative: bool


class AvailabilityEntry(Schema):
    id: str
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
    status: str
    # Cancelled or rejected: there is nothing to answer any more.
    cancelled: bool


class RsvpAnswer(Schema):
    status: Literal["accepted", "tentative", "declined"]
