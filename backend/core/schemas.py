"""
Django Ninja schemas mirroring the FastAPI API contract.
"""

from datetime import datetime
from typing import Annotated, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ninja import Field, Schema
from pydantic import AfterValidator, model_validator


Weekday = Annotated[int, Field(ge=0, le=6)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


def _known_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown time zone")
    return name


TimeZoneName = Annotated[str, AfterValidator(_known_zone)]


# ---------------------------------------------------------------------------
# Auth & users
# ---------------------------------------------------------------------------


class UserOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    email: str
    display_name: str
    is_admin: bool
    is_staff: bool
    is_superuser: bool
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
    invitations: Optional[bool] = None
    responses: Optional[bool] = None
    approvals: Optional[bool] = None
    decisions: Optional[bool] = None
    comments: Optional[bool] = None
    memberships: Optional[bool] = None
    reminders: Optional[bool] = None


class ProfileOut(UserOut):
    email_notifications: EmailNotifications


class UserUpdate(Schema):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    time_format: Optional[Literal["auto", "24h", "12h"]] = None
    date_format: Optional[Literal["auto", "dmy", "mdy", "ymd"]] = None
    timezone: Optional[TimeZoneName] = None
    language: Optional[Literal["en", "de"]] = None
    email_notifications: Optional[EmailNotificationsUpdate] = None


class OverviewSettingsOut(Schema):
    model_config = {"from_attributes": True}

    first_weekday: int
    show_weekends: bool
    weekend_days: List[Weekday]
    show_week_numbers: bool
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
    first_weekday: Optional[int] = Field(None, ge=0, le=6)
    show_weekends: Optional[bool] = None
    weekend_days: Optional[List[Weekday]] = None
    show_week_numbers: Optional[bool] = None
    use_calendar_colors: Optional[bool] = None
    base_color: Optional[Color] = None
    weekend_color: Optional[Color] = None
    today_color: Optional[Color] = None
    event_color: Optional[Color] = None
    border_color: Optional[Color] = None
    outer_border_color: Optional[Color] = None
    dark_base_color: Optional[Color] = None
    dark_weekend_color: Optional[Color] = None
    dark_today_color: Optional[Color] = None
    dark_event_color: Optional[Color] = None
    dark_border_color: Optional[Color] = None
    dark_outer_border_color: Optional[Color] = None


class AppPasswordCreate(Schema):
    label: str = Field(..., min_length=1, max_length=255)


class AppPasswordOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    label: str
    last_used_at: Optional[datetime] = None
    created_at: datetime


class AppPasswordCreated(Schema):
    id: str
    label: str
    password: str


class SearchResult(Schema):
    id: str
    type: str
    label: str
    subtitle: Optional[str] = None
    meta: Optional[dict] = None


class GroupOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    name: str
    description: Optional[str] = None
    member_count: int = 0


class GroupMemberOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    email: str
    display_name: str


class GroupDetailOut(GroupOut):
    members: List[GroupMemberOut] = []


class GroupCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    member_ids: List[str] = []


class GroupUpdate(Schema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    # Replaces the member list when given.
    member_ids: Optional[List[str]] = None


class AdminUserOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    email: str
    display_name: str
    is_admin: bool
    is_staff: bool
    is_superuser: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    groups: List[GroupOut] = []


class AdminUserCreate(Schema):
    email: str = Field(..., pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    is_admin: bool = False
    is_staff: bool = False
    is_superuser: bool = False
    is_active: bool = True
    group_ids: Optional[List[str]] = None


class AdminUserUpdate(Schema):
    email: Optional[str] = Field(None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8)
    is_admin: Optional[bool] = None
    is_staff: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_active: Optional[bool] = None
    group_ids: Optional[List[str]] = None


class AdminPasswordResetOut(Schema):
    password: str


class AppSettingsOut(Schema):
    model_config = {"from_attributes": True}

    id: int
    app_name: str
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    default_first_weekday: int
    default_show_weekends: bool
    default_weekend_days: List[int]
    default_show_week_numbers: bool


class AppSettingsUpdate(Schema):
    app_name: Optional[str] = Field(None, min_length=1, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=1_000_000)
    favicon_url: Optional[str] = Field(None, max_length=1_000_000)
    default_first_weekday: Optional[int] = Field(None, ge=0, le=6)
    default_show_weekends: Optional[bool] = None
    default_weekend_days: Optional[List[int]] = None
    default_show_week_numbers: Optional[bool] = None


# ---------------------------------------------------------------------------
# Calendar folders
# ---------------------------------------------------------------------------


class FolderCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[str] = None
    position: int = 0


class FolderUpdate(Schema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[str] = None
    position: Optional[int] = None


class FolderOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    name: str
    parent_id: Optional[str]
    position: int


# ---------------------------------------------------------------------------
# Calendar members
# ---------------------------------------------------------------------------


class CalendarMemberCreate(Schema):
    user_id: str
    role: str = "read"


class CalendarMemberUpdate(Schema):
    role: Optional[str] = None


class CalendarMemberBatchOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    calendar_id: str
    user_id: str
    role: str
    folder_id: Optional[str]
    position: int


class CalendarMemberOut(CalendarMemberBatchOut):
    email: str
    display_name: str


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


class CalendarCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    force_all_day: bool = False
    first_weekday: Optional[int] = Field(None, ge=0, le=6)
    show_weekends: Optional[bool] = None
    weekend_days: Optional[List[Weekday]] = None
    show_week_numbers: Optional[bool] = None
    # Colors left out start with the default preset.
    base_color: Optional[Color] = None
    weekend_color: Optional[Color] = None
    today_color: Optional[Color] = None
    event_color: Optional[Color] = None
    border_color: Optional[Color] = None
    outer_border_color: Optional[Color] = None
    dark_base_color: Optional[Color] = None
    dark_weekend_color: Optional[Color] = None
    dark_today_color: Optional[Color] = None
    dark_event_color: Optional[Color] = None
    dark_border_color: Optional[Color] = None
    dark_outer_border_color: Optional[Color] = None


class CalendarUpdate(Schema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    url_path: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    force_all_day: Optional[bool] = None
    first_weekday: Optional[int] = Field(None, ge=0, le=6)
    show_weekends: Optional[bool] = None
    weekend_days: Optional[List[Weekday]] = None
    show_week_numbers: Optional[bool] = None
    base_color: Optional[Color] = None
    weekend_color: Optional[Color] = None
    today_color: Optional[Color] = None
    event_color: Optional[Color] = None
    border_color: Optional[Color] = None
    outer_border_color: Optional[Color] = None
    dark_base_color: Optional[Color] = None
    dark_weekend_color: Optional[Color] = None
    dark_today_color: Optional[Color] = None
    dark_event_color: Optional[Color] = None
    dark_border_color: Optional[Color] = None
    dark_outer_border_color: Optional[Color] = None
    is_public: Optional[bool] = None
    public_role: Optional[Literal["read", "own", "full"]] = None


class CalendarOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    name: str
    description: Optional[str]
    url_path: Optional[str]
    force_all_day: bool
    first_weekday: int
    show_weekends: bool
    weekend_days: List[Weekday]
    show_week_numbers: bool
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
    my_membership: Optional[CalendarMemberOut] = None


class CalendarListOut(Schema):
    calendar: CalendarOut
    membership: CalendarMemberOut


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
    model_config = {"from_attributes": True}

    id: str
    group: CalendarGroupLinkGroupInfo
    role: str
    # Everyone in the group, who therefore has the role in this calendar.
    members: list[CalendarGroupLinkMember]


class CalendarGroupLinkCreate(Schema):
    group_id: str
    role: Literal["read", "own", "full"] = "read"


class CalendarGroupLinkUpdate(Schema):
    role: Optional[Literal["read", "own", "full"]] = None


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ApproversIn(Schema):
    """The complete list of approvers; whoever is not in it is no approver any more."""

    user_ids: List[str]


class ApproverOut(Schema):
    user_id: str
    email: str
    display_name: str


# An icon's name: lower-case words joined by hyphens, or empty for none. Which names exist is up to the client.
ResourceIconName = Annotated[str, Field(max_length=40, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$|^$")]


class ResourceCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = "#f59e0b"
    icon: ResourceIconName = ""
    requires_approval: bool = False
    is_location: bool = False
    is_active: bool = True


class ResourceUpdate(Schema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[ResourceIconName] = None
    requires_approval: Optional[bool] = None
    is_location: Optional[bool] = None
    is_active: Optional[bool] = None


class ResourceOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    calendar_id: str
    name: str
    description: Optional[str]
    color: str
    icon: str
    requires_approval: bool
    is_location: bool
    is_active: bool
    approvers: List[ApproverOut]
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
    description: Optional[str] = None
    color: str = "#64748b"


class CategoryUpdate(Schema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None


class CategoryOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    calendar_id: str
    name: str
    description: Optional[str]
    color: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventParticipantInvite(Schema):
    user_id: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "needs_action"

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> "EventParticipantInvite":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        return self


class EventCreate(Schema):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    # A resource marked as location to book; the location then is its name.
    location_resource_id: Optional[str] = None
    start: datetime
    end: datetime
    all_day: bool = False
    timezone: Optional[TimeZoneName] = None
    show_recurrence_count: bool = False
    rrule: Optional[str] = None
    category_id: Optional[str] = None
    resource_id: Optional[str] = None
    participants: Optional[List[EventParticipantInvite]] = None


class EventUpdate(Schema):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    location_resource_id: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    all_day: Optional[bool] = None
    timezone: Optional[TimeZoneName] = None
    show_recurrence_count: Optional[bool] = None
    rrule: Optional[str] = None
    category_id: Optional[str] = None
    resource_id: Optional[str] = None


class EventParticipantCreate(Schema):
    user_id: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "needs_action"

    @model_validator(mode="after")
    def require_user_id_or_email(self) -> "EventParticipantCreate":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        return self


class EventRemindersIn(Schema):
    # Minutes before each occurrence's start; 0 is at the start.
    minutes: List[int]


class EventRemindersOut(Schema):
    minutes: List[int]


class EventParticipantUpdate(Schema):
    status: Optional[str] = None


class EventParticipantOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    event_id: str
    user_id: Optional[str]
    email: str
    display_name: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class EventOut(Schema):
    model_config = {"from_attributes": True}

    id: str
    calendar_id: str
    creator_id: str
    creator_name: Optional[str] = None
    creator_email: Optional[str] = None
    title: str
    description: Optional[str]
    location: str = ""
    location_resource_id: Optional[str] = None
    location_resource_name: Optional[str] = None
    start: datetime
    end: datetime
    all_day: bool
    timezone: str
    show_recurrence_count: bool
    rrule: Optional[str]
    # Extra occurrence starts besides those of the rule (RDATE), e.g. from other clients.
    rdates: List[datetime] = []
    uid: str
    # Set when the event is a changed occurrence of the series parent_id.
    parent_id: Optional[str] = None
    recurrence_id: Optional[datetime] = None
    category_id: Optional[str]
    category_name: Optional[str]
    category_color: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    status: str
    # Names of the booked resources a pending event still waits to have approved.
    awaiting_approval: List[str] = []
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    decision_note: Optional[str]
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
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    recurrence_count: Optional[int]
    status: str
    category_id: Optional[str]
    category_name: Optional[str]
    category_color: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    resource_icon: str = ""
    location: str = ""
    location_resource_id: Optional[str] = None
    location_resource_icon: str = ""
    creator_id: str
    can_edit: bool
    is_recurring: bool
    # For occurrences of a series: the series and the occurrence's original start, which
    # identify it in /events/{series_id}/occurrences/{recurrence_id}.
    series_id: Optional[str] = None
    recurrence_id: Optional[datetime] = None


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
    actor_id: Optional[str]
    actor_name: Optional[str]
    action: str
    details: Optional[dict]
    created_at: datetime


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(Schema):
    id: str
    type: str
    actor_id: Optional[str]
    actor_name: Optional[str]
    calendar_id: Optional[str]
    event_id: Optional[str]
    title: str
    data: Optional[dict]
    read_at: Optional[datetime]
    created_at: datetime
    # Current status of the linked event and, for invitations, the user's own answer.
    event_status: Optional[str] = None
    response_status: Optional[str] = None
    deletable: bool = True


class NotificationUpdate(Schema):
    read: bool


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalAction(Schema):
    note: Optional[str] = None


class ApprovalOut(EventOut):
    approver_pool: List[ApproverOut]


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
    parent_id: Optional[str] = None


class LayoutItemsUpdate(Schema):
    items: List[LayoutItem]


class LayoutOut(Schema):
    folders: List[FolderOut]
    calendars: List[CalendarListOut]


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


class BookingConflict(Schema):
    message: str = "Resource booking conflict"
    conflicts: List[dict]


class BusyPeriod(Schema):
    start: datetime
    end: datetime
    # Pending bookings and invitations not answered yet.
    tentative: bool


class AvailabilityEntry(Schema):
    id: str
    name: str
    busy: List[BusyPeriod]


class AvailabilityOut(Schema):
    users: List[AvailabilityEntry]
    resources: List[AvailabilityEntry]


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
    description: Optional[str] = None
    rrule: Optional[str] = None
    organizer_name: str
    email: str
    status: str
    # Cancelled or rejected: there is nothing to answer any more.
    cancelled: bool


class RsvpAnswer(Schema):
    status: Literal["accepted", "tentative", "declined"]
