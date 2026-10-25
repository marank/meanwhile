"""
Administration: users and app settings.
"""

from datetime import datetime

from ninja import Field

from core.schemas.common import Id, Schema, Text
from core.schemas.groups import GroupOut


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
