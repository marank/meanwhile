from fastapi import HTTPException, status

from app.models import Calendar, CalendarMember, Role


ROLE_ORDER = [Role.VIEWER, Role.CONTRIBUTOR, Role.EDITOR, Role.OWNER]


def role_weight(role: Role) -> int:
    return ROLE_ORDER.index(role)


def has_at_least_role(member: CalendarMember, role: Role) -> bool:
    return role_weight(Role(member.role)) >= role_weight(role)


def get_membership(db, calendar_id: str, user_id: str) -> CalendarMember | None:
    return (
        db.query(CalendarMember)
        .filter_by(calendar_id=calendar_id, user_id=user_id)
        .first()
    )


def require_membership(db, calendar_id: str, user_id: str) -> CalendarMember:
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
