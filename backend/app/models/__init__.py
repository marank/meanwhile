import enum
from datetime import datetime, timezone
from typing import List, Optional

import uuid_utils
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class EventStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    calendars_owned: Mapped[List["Calendar"]] = relationship(
        back_populates="owner", foreign_keys="Calendar.owner_id"
    )
    memberships: Mapped[List["CalendarMember"]] = relationship(back_populates="user")
    folders: Mapped[List["Folder"]] = relationship(back_populates="user")
    app_passwords: Mapped[List["AppPassword"]] = relationship(back_populates="user")
    created_events: Mapped[List["Event"]] = relationship(
        back_populates="creator", foreign_keys="Event.creator_id"
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    app_name: Mapped[str] = mapped_column(String(255), default="Calendar", nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_first_weekday: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    default_show_weekends: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_weekend_days: Mapped[List[int]] = mapped_column(JSON, default=lambda: [0, 6], nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


def get_or_create_app_settings(db: Session) -> "AppSettings":
    settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if settings is None:
        settings = AppSettings()
        db.add(settings)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            settings = db.query(AppSettings).filter(AppSettings.id == 1).one()
        db.refresh(settings)
    return settings


class AppPassword(Base):
    __tablename__ = "app_passwords"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="app_passwords")


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="folders")
    children: Mapped[List["Folder"]] = relationship(back_populates="parent")
    parent: Mapped[Optional["Folder"]] = relationship(
        back_populates="children", remote_side=[id]
    )
    memberships: Mapped[List["CalendarMember"]] = relationship(
        back_populates="folder", foreign_keys="CalendarMember.folder_id"
    )


class Calendar(Base):
    __tablename__ = "calendars"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    dark_color: Mapped[str] = mapped_column(String(7), default="#60a5fa", nullable=False)
    force_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_weekday: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    show_weekends: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekend_days: Mapped[List[int]] = mapped_column(JSON, default=lambda: [0, 6], nullable=False)
    today_color: Mapped[str] = mapped_column(String(7), default="#eff6ff", nullable=False)
    dark_today_color: Mapped[str] = mapped_column(String(7), default="#27272a", nullable=False)
    weekend_color: Mapped[str] = mapped_column(String(7), default="#f9fafb", nullable=False)
    dark_weekend_color: Mapped[str] = mapped_column(String(7), default="#18181b", nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    feed_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    owner: Mapped["User"] = relationship(
        back_populates="calendars_owned", foreign_keys=[owner_id]
    )
    members: Mapped[List["CalendarMember"]] = relationship(back_populates="calendar")
    approvers: Mapped[List["CalendarApprover"]] = relationship(
        back_populates="calendar"
    )
    resources: Mapped[List["Resource"]] = relationship(back_populates="calendar")
    categories: Mapped[List["Category"]] = relationship(back_populates="calendar")
    events: Mapped[List["Event"]] = relationship(back_populates="calendar")


class CalendarMember(Base):
    __tablename__ = "calendar_members"
    __table_args__ = (
        UniqueConstraint("calendar_id", "user_id", name="uq_calendar_member"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default=Role.VIEWER.value)
    folder_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    calendar: Mapped["Calendar"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")
    folder: Mapped[Optional["Folder"]] = relationship(
        back_populates="memberships", foreign_keys=[folder_id]
    )


class CalendarApprover(Base):
    __tablename__ = "calendar_approvers"
    __table_args__ = (
        UniqueConstraint(
            "calendar_id", "user_id", name="uq_calendar_approver"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    calendar: Mapped["Calendar"] = relationship(back_populates="approvers")
    user: Mapped["User"] = relationship()


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#f59e0b")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    calendar: Mapped["Calendar"] = relationship(back_populates="resources")
    events: Mapped[List["Event"]] = relationship(back_populates="resource")
    approvers: Mapped[List["ResourceApprover"]] = relationship(
        back_populates="resource"
    )


class ResourceApprover(Base):
    __tablename__ = "resource_approvers"
    __table_args__ = (
        UniqueConstraint(
            "resource_id", "user_id", name="uq_resource_approver"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    resource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    resource: Mapped["Resource"] = relationship(back_populates="approvers")
    user: Mapped["User"] = relationship()


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("calendar_id", "name", name="uq_category_calendar_name"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#64748b")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    calendar: Mapped["Calendar"] = relationship(back_populates="categories")
    events: Mapped[List["Event"]] = relationship(back_populates="category")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_utils.uuid7())
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    creator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    show_recurrence_count: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rrule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uid: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    raw_ical: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default=EventStatus.CONFIRMED.value, nullable=False
    )
    decided_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    calendar: Mapped["Calendar"] = relationship(back_populates="events")
    creator: Mapped["User"] = relationship(
        back_populates="created_events", foreign_keys=[creator_id]
    )
    resource: Mapped[Optional["Resource"]] = relationship(back_populates="events")
    category: Mapped[Optional["Category"]] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("calendar_id", "uid", name="uq_event_calendar_uid"),
    )
