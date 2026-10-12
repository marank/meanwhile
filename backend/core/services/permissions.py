"""
Permission helpers for calendars and events.
"""

from dataclasses import dataclass

from django.db.models import Q
from ninja.errors import HttpError

from core.models.base import EventStatus, MembershipSource, Role
from core.models.calendars import Calendar, CalendarGroup, CalendarMember
from core.models.events import Event, EventParticipant
from core.models.users import User
from core.services.bookings import is_in_approver_pool

ROLE_ORDER = [Role.READ, Role.OWN, Role.FULL, Role.MANAGE, Role.OWNER]


def role_weight(role: str) -> int:
    return ROLE_ORDER.index(role)


def has_at_least_role(member, role: str) -> bool:
    return role_weight(member.role) >= role_weight(role)


@dataclass
class MembershipInfo:
    """Lightweight stand-in for a direct or derived calendar membership."""

    id: str
    calendar_id: str
    user_id: str
    role: str
    folder_id: str | None
    position: int
    calendar: Calendar
    user: User


def _synthetic(calendar: Calendar, user: User, role: str) -> MembershipInfo:
    return MembershipInfo(
        id="",
        calendar_id=str(calendar.id),
        user_id=str(user.id),
        role=role,
        folder_id=None,
        position=0,
        calendar=calendar,
        user=user,
    )


def get_direct_membership(calendar_id: str, user_id: str) -> CalendarMember | None:
    """The membership granted to the user by hand (or theirs as the owner), not one from a group or added."""
    return CalendarMember.objects.filter(
        calendar_id=calendar_id, user_id=user_id, source=MembershipSource.DIRECT
    ).first()


def get_membership(calendar: Calendar, user: User) -> MembershipInfo | None:
    """The user's access to the calendar; see memberships_of."""
    return memberships_of(user, [calendar]).get(calendar.id)


def memberships_of(user: User, calendars) -> dict[str, MembershipInfo]:
    """
    The user's access to each of the calendars they have access to, by calendar id; in at most two queries.

    A direct membership's role applies as it is. Otherwise the best role of the user's groups, else the
    public role, is worked out here every time: a membership from a group or a public calendar only
    remembers where it sits in the sidebar, so access never depends on keeping it in step.
    """
    calendars = {c.id: c for c in calendars}
    rows = {m.calendar_id: m for m in CalendarMember.objects.filter(calendar_id__in=calendars, user_id=user.id)}
    direct = {calendar_id for calendar_id, row in rows.items() if row.source == MembershipSource.DIRECT}
    # Groups only matter where the user has no direct membership.
    others = [calendar_id for calendar_id in calendars if calendar_id not in direct]
    group_roles: dict[str, str] = {}
    if others:
        links = CalendarGroup.objects.filter(calendar_id__in=others, group__in=user.groups.all())
        for calendar_id, role in links.values_list("calendar_id", "role"):
            if calendar_id not in group_roles or role_weight(role) > role_weight(group_roles[calendar_id]):
                group_roles[calendar_id] = role

    result = {}
    for calendar_id, calendar in calendars.items():
        row = rows.get(calendar_id)
        if row is not None and row.source == MembershipSource.DIRECT:
            role = row.role
        elif calendar_id in group_roles:
            role = group_roles[calendar_id]
        elif calendar.is_public:
            role = calendar.public_role
        else:
            continue
        result[calendar_id] = _from_row(row, role, calendar, user) if row else _synthetic(calendar, user, role)
    return result


def _from_row(membership: CalendarMember, role: str, calendar: Calendar, user: User) -> MembershipInfo:
    return MembershipInfo(
        id=str(membership.id),
        calendar_id=str(membership.calendar_id),
        user_id=str(membership.user_id),
        role=role,
        folder_id=str(membership.folder_id) if membership.folder_id else None,
        position=membership.position,
        calendar=calendar,
        user=user,
    )


def can_modify_event(event: Event, user_id: str, role: str) -> bool:
    """With "full" access every event, with "own" only those the user created."""
    return role_weight(role) >= role_weight(Role.FULL) or event.creator_id == user_id


def is_owner(member) -> bool:
    return member.role == Role.OWNER


def can_manage(member) -> bool:
    """Calendar settings, access, feed and approvers; only deleting the calendar stays with its owner."""
    return has_at_least_role(member, Role.MANAGE)


def get_member_calendar(
    calendar_id: str, user: User, role: str = Role.READ, denied: str = "Your role doesn't allow this"
) -> tuple[Calendar, MembershipInfo]:
    """The calendar and the user's membership of it, which must have at least `role`.

    An unknown calendar is answered with 404 (see core.api), one the user has no access to with 403,
    as is a lesser role, then with the message `denied`.
    """
    calendar = Calendar.objects.get(id=calendar_id)
    membership = get_membership(calendar, user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not has_at_least_role(membership, role):
        raise HttpError(403, denied)
    return calendar, membership


def get_visible_event(event_id: str, user: User) -> tuple[Event, MembershipInfo]:
    event = Event.objects.select_related("creator").get(id=event_id)
    membership = get_membership(event.calendar, user)
    if membership is None:
        raise HttpError(404, "Event not found")

    if not can_see_event(event, user, membership):
        raise HttpError(404, "Event not found")
    return event, membership


def participant_event_ids(user: User) -> set[str]:
    """Events the user is invited to, by account or by email address."""
    return set(
        EventParticipant.objects.filter(Q(user=user) | Q(email__iexact=user.email))
        .values_list("event_id", flat=True)
    )


def can_see_event(event: Event, user: User, membership) -> bool:
    user_id = str(user.id)
    if str(event.creator_id) == user_id:
        return True
    if event.status == EventStatus.PENDING:
        # Pending bookings are private to the requester, participants and approvers.
        return event.id in participant_event_ids(user) or is_in_approver_pool(event, user_id)
    if event.status in {EventStatus.REJECTED, EventStatus.CANCELLED}:
        return has_at_least_role(membership, Role.FULL)
    return True


def accessible_calendars(user: User):
    """Calendars the user can read: own, shared directly or via a group, and public ones."""
    return Calendar.objects.filter(
        Q(owner=user)
        | Q(members__user=user)
        | Q(calendar_groups__group__in=user.groups.all())
        | Q(is_public=True)
    ).distinct()


def sidebar_calendars(user: User):
    """The calendars in the user's sidebar (and CalDAV clients): those they have a membership of, from a group,
    added or granted directly. Other public calendars can be read, but have to be added first."""
    return Calendar.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()
