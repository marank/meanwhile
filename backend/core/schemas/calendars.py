"""
Calendars, their folders, members, group links, sidebar layout and feeds.
"""

from datetime import datetime
from typing import Literal

from ninja import Field

from core.models.base import Role
from core.schemas.common import Color, GrantableRole, Id, PublicRole, Schema, Text, Weekday
from core.schemas.layout import WeekLayoutOut

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
# Feed
# ---------------------------------------------------------------------------


class FeedUrlOut(Schema):
    feed_url: str


class FeedTokenRotateOut(Schema):
    feed_url: str
