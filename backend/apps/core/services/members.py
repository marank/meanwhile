"""
Direct members of a calendar: granting a role, changing it and taking it away, with the notifications
and clean-ups that go with it. Memberships from a group or a public calendar: apps.core.services.memberships.
"""

from ninja.errors import HttpError

from apps.core.models import (
    Calendar,
    CalendarApprover,
    CalendarMember,
    FeedToken,
    ResourceApprover,
    User,
)
from apps.core.models.base import MembershipSource, Role
from apps.core.services.memberships import next_sidebar_position, sync_membership
from apps.core.services.notifications import notify
from apps.core.services.permissions import get_direct_membership, get_membership, role_weight


def add_member(calendar: Calendar, actor: User, user_id: str, role: str) -> CalendarMember:
    if role == Role.OWNER:
        raise HttpError(400, "Cannot add a second owner")
    if get_direct_membership(calendar.id, user_id):
        raise HttpError(400, "User is already a member")

    user = User.objects.get(id=user_id)
    # Who has the calendar through a group or added it keeps its place in their sidebar.
    member = CalendarMember.objects.filter(calendar=calendar, user=user).first()
    if member is None:
        member = CalendarMember.objects.create(
            calendar=calendar, user=user, role=role, position=next_sidebar_position(user.id)
        )
    else:
        member.source, member.role = MembershipSource.DIRECT, role
        member.save(update_fields=["source", "role"])
    notify(
        [user_id],
        "member_added",
        str(actor.id),
        calendar.name,
        calendar_id=str(calendar.id),
        data={"role": role},
    )
    return member


def _direct_member(calendar: Calendar, user_id: str) -> CalendarMember:
    member = get_direct_membership(calendar.id, user_id)
    if member is None:
        raise HttpError(404, "Member not found")
    return member


def change_role(calendar: Calendar, actor: User, user_id: str, role: str) -> CalendarMember:
    member = _direct_member(calendar, user_id)
    if member.role == Role.OWNER:
        raise HttpError(400, "Owner role cannot be changed")
    if role == Role.OWNER:
        raise HttpError(400, "Cannot make a second owner")
    if member.role != role:
        promoted = member.role is None or role_weight(role) > role_weight(member.role)
        member.role = role
        member.save()
        notify(
            [user_id],
            "member_role_changed",
            str(actor.id),
            calendar.name,
            calendar_id=str(calendar.id),
            data={"role": role, "promoted": promoted},
        )
    return member


def remove_member(calendar: Calendar, user_id: str) -> None:
    member = _direct_member(calendar, user_id)
    if member.role == Role.OWNER:
        raise HttpError(400, "Cannot remove the owner")
    user = member.user
    # What the user still has through a group (or, a public calendar in their sidebar, its public role)
    # takes the membership's place; with nothing left it goes.
    sync_membership(user.id, calendar, release_direct=True)
    # Someone with no access left (not through a group or a public calendar either) can't decide on
    # bookings any more, so they stop being an approver, too.
    if get_membership(calendar, user) is None:
        CalendarApprover.objects.filter(calendar=calendar, user=user).delete()
        ResourceApprover.objects.filter(resource__calendar=calendar, user=user).delete()
        # And their feed URL goes for good: added again later, they get a new one.
        FeedToken.objects.filter(calendar=calendar, user=user).delete()
