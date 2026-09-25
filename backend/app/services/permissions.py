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
    member = get_membership(db, calendar_id, user_id)
    if member is None:
        raise PermissionError("Not a member of this calendar")
    return member


def is_owner(member: CalendarMember) -> bool:
    return member.role == Role.OWNER.value
