"""
Permission helpers for calendars and events.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ninja.errors import HttpError

from core.models.base import EventStatus, Role
from core.models.calendars import Calendar, CalendarGroup, CalendarMember
from django.db.models import Q

from core.models.events import Event, EventParticipant
from core.services.bookings import is_in_approver_pool
from core.models.users import User

if TYPE_CHECKING:
    pass


ROLE_ORDER = [Role.VIEWER, Role.CONTRIBUTOR, Role.EDITOR, Role.OWNER]


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
    return CalendarMember.objects.filter(
        calendar_id=calendar_id, user_id=user_id
    ).first()


def get_membership(calendar: Calendar, user: User) -> MembershipInfo | None:
    direct = get_direct_membership(calendar.id, user.id)
    if direct is not None:
        return MembershipInfo(
            id=str(direct.id),
            calendar_id=str(direct.calendar_id),
            user_id=str(direct.user_id),
            role=direct.role,
            folder_id=str(direct.folder_id) if direct.folder_id else None,
            position=direct.position,
            calendar=calendar,
            user=user,
        )

    user_group_ids = user.groups.values_list("id", flat=True)
    group_links = CalendarGroup.objects.filter(
        calendar=calendar, group_id__in=user_group_ids
    )
    if group_links.exists():
        best_role = max(group_links, key=lambda gl: role_weight(gl.role))
        return _synthetic(calendar, user, best_role.role)

    if calendar.is_public:
        return _synthetic(calendar, user, calendar.public_role)

    return None


def is_owner(member) -> bool:
    return member.role == Role.OWNER


def get_visible_event(event_id: str, user: User) -> tuple[Event, MembershipInfo]:
    try:
        event = Event.objects.select_related("creator").get(id=event_id)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")

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
        return event.id in participant_event_ids(user) or is_in_approver_pool(event, user_id=user_id)
    if event.status in {EventStatus.REJECTED, EventStatus.CANCELLED}:
        return has_at_least_role(membership, Role.EDITOR)
    return True


def accessible_calendars(user: User):
    """Calendars the user can read: own, shared directly or via a group, and public ones."""
    return Calendar.objects.filter(
        Q(owner=user)
        | Q(members__user=user)
        | Q(calendar_groups__group__in=user.groups.all())
        | Q(is_public=True)
    ).distinct()
