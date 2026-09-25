from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Weekday = Annotated[int, Field(ge=0, le=6)]


# ---------------------------------------------------------------------------
# Auth & users
# ---------------------------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)


class AppPasswordCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class AppPasswordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    last_used_at: Optional[datetime] = None
    created_at: datetime


class AppPasswordCreated(BaseModel):
    id: str
    label: str
    password: str


class UserSearchResult(BaseModel):
    id: str
    email: str
    display_name: str


# ---------------------------------------------------------------------------
# Calendar folders
# ---------------------------------------------------------------------------


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[str] = None
    position: int = 0


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[str] = None
    position: Optional[int] = None


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    parent_id: Optional[str]
    position: int


# ---------------------------------------------------------------------------
# Calendar members
# ---------------------------------------------------------------------------


class CalendarMemberCreate(BaseModel):
    user_id: str
    role: str = "viewer"


class CalendarMemberUpdate(BaseModel):
    role: Optional[str] = None
    folder_id: Optional[str] = None
    position: Optional[int] = None


class CalendarMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    calendar_id: str
    user_id: str
    email: str
    display_name: str
    role: str
    folder_id: Optional[str]
    position: int


class MyMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    folder_id: Optional[str]
    position: int


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


class CalendarCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"
    dark_color: str = "#60a5fa"
    force_all_day: bool = False
    first_weekday: int = Field(0, ge=0, le=6)
    show_weekends: bool = True
    weekend_days: List[Weekday] = Field(default_factory=lambda: [0, 6])
    today_color: str = "#eff6ff"
    dark_today_color: str = "#27272a"
    weekend_color: str = "#f9fafb"
    dark_weekend_color: str = "#18181b"


class CalendarUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None
    dark_color: Optional[str] = None
    force_all_day: Optional[bool] = None
    first_weekday: Optional[int] = Field(None, ge=0, le=6)
    show_weekends: Optional[bool] = None
    weekend_days: Optional[List[Weekday]] = None
    today_color: Optional[str] = None
    dark_today_color: Optional[str] = None
    weekend_color: Optional[str] = None
    dark_weekend_color: Optional[str] = None


class CalendarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    color: str
    dark_color: str
    force_all_day: bool
    first_weekday: int
    show_weekends: bool
    weekend_days: List[Weekday]
    today_color: str
    dark_today_color: str
    weekend_color: str
    dark_weekend_color: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    my_membership: Optional[CalendarMemberOut] = None


class CalendarListOut(BaseModel):
    calendar: CalendarOut
    membership: CalendarMemberOut


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ApproverCreate(BaseModel):
    user_id: str


class ApproverOut(BaseModel):
    user_id: str
    email: str
    display_name: str


class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = "#f59e0b"
    requires_approval: bool = False


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None
    requires_approval: Optional[bool] = None
    is_active: Optional[bool] = None


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    calendar_id: str
    name: str
    description: Optional[str]
    color: str
    requires_approval: bool
    is_active: bool
    approvers: List[ApproverOut]
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: str = "#64748b"


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start: datetime
    end: datetime
    all_day: bool = False
    show_recurrence_count: bool = False
    rrule: Optional[str] = None
    category_id: Optional[str] = None
    resource_id: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    all_day: Optional[bool] = None
    show_recurrence_count: Optional[bool] = None
    rrule: Optional[str] = None
    category_id: Optional[str] = None
    resource_id: Optional[str] = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    calendar_id: str
    creator_id: str
    title: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    show_recurrence_count: bool
    rrule: Optional[str]
    uid: str
    category_id: Optional[str]
    category_name: Optional[str]
    category_color: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    status: str
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    decision_note: Optional[str]
    created_at: datetime
    updated_at: datetime


class OccurrenceOut(BaseModel):
    event_id: str
    title: str
    description: Optional[str]
    start: datetime
    end: datetime
    all_day: bool
    recurrence_count: Optional[int]
    status: str
    color: Optional[str]
    dark_color: Optional[str]
    category_id: Optional[str]
    category_name: Optional[str]
    category_color: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    creator_id: str


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalAction(BaseModel):
    note: Optional[str] = None


class ApprovalOut(EventOut):
    approver_pool: List[ApproverOut]


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


class FeedUrlOut(BaseModel):
    feed_url: str


class FeedTokenRotateOut(BaseModel):
    feed_url: str
