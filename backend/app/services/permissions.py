import uuid_utils
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Calendar,
    CalendarGroup,
    CalendarMember,
    Event,
    EventStatus,
    Role,
    User,
    user_group_members,
)


ROLE_ORDER = [Role.VIEWER, Role.CONTRIBUTOR, Role.EDITOR, Role.OWNER]


def role_weight(role: Role) -> int:
    return ROLE_ORDER.index(role)


def has_at_least_role(member: CalendarMember, role: Role) -> bool:
    return role_weight(Role(member.role)) >= role_weight(role)


class _SyntheticMember:
    """Lightweight stand-in for CalendarMember that is never added to a session.

    It carries the same attributes that ``_serialize_membership`` and the
    permission helpers read, but avoids touching any SQLAlchemy relationship
    collections (which would cascade the object into the session).
    """

    __slots__ = (
        "id", "calendar_id", "user_id", "role",
        "folder_id", "position", "calendar", "user",
    )

    def __init__(
        self,
        *,
        calendar: Calendar,
        user: User,
        role: str,
    ):
        self.id = str(uuid_utils.uuid7())
        self.calendar_id = calendar.id
        self.user_id = user.id
        self.role = role
        self.folder_id = None
        self.position = 0
        self.calendar = calendar
        self.user = user


def _make_synthetic_member(
    calendar: Calendar, user: User, role_value: str
) -> "_SyntheticMember":
    """Build a lightweight membership stand-in (never persisted)."""
    return _SyntheticMember(calendar=calendar, user=user, role=role_value)


def get_direct_membership(
    db: Session, calendar_id: str, user_id: str
) -> CalendarMember | None:
    """Return the direct CalendarMember row, or None."""
    return (
        db.query(CalendarMember)
        .filter_by(calendar_id=calendar_id, user_id=user_id)
        .first()
    )


def get_membership(db: Session, calendar_id: str, user_id: str) -> CalendarMember | None:
    # 1. Direct membership always wins.
    direct = get_direct_membership(db, calendar_id, user_id)
    if direct is not None:
        return direct

    calendar = db.query(Calendar).filter(Calendar.id == calendar_id).first()
    if calendar is None:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    # 2. Group links: find the highest role among matching links.
    user_group_ids = (
        select(user_group_members.c.group_id)
        .where(user_group_members.c.user_id == user_id)
        .scalar_subquery()
    )
    group_links = (
        db.query(CalendarGroup)
        .filter(
            CalendarGroup.calendar_id == calendar_id,
            CalendarGroup.group_id.in_(user_group_ids),
        )
        .all()
    )
    if group_links:
        best_role = max(group_links, key=lambda gl: role_weight(Role(gl.role)))
        return _make_synthetic_member(calendar, user, best_role.role)

    # 3. Public calendar fallback.
    if calendar.is_public:
        return _make_synthetic_member(calendar, user, calendar.public_role)

    return None


def require_membership(db: Session, calendar_id: str, user_id: str) -> CalendarMember:
    calendar = db.query(Calendar).filter(Calendar.id == calendar_id).first()
    if calendar is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calendar not found"
        )
    member = get_membership(db, calendar_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this calendar",
        )
    return member


def is_owner(member: CalendarMember) -> bool:
    return member.role == Role.OWNER.value


def get_visible_event(db: Session, event_id: str, user: User) -> tuple[Event, CalendarMember]:
    event = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.id == event_id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_membership(db, event.calendar_id, user.id)
    if event.status in {EventStatus.CANCELLED.value, EventStatus.REJECTED.value}:
        if event.creator_id != user.id and not has_at_least_role(
            membership, Role.EDITOR
        ):
            raise HTTPException(status_code=404, detail="Event not found")
    return event, membership
