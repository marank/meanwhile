"""
Memberships that come from a group or from a public calendar, kept in step with their source.

Every calendar in a user's sidebar is one membership of theirs (CalendarMember): it holds where the calendar
sits. Direct ones are granted by hand, with a role; the others are made and removed here whenever what they
come from changes, and their role is what that gives (see get_membership). A direct membership wins over a
group, a group over a public calendar.
"""

from collections.abc import Iterable
from uuid import UUID

from django.db.models import Max

from core.models import Calendar, CalendarGroup, CalendarMember, Folder, MembershipSource, User
from core.models.base import AnyId


def next_sidebar_position(user_id: AnyId) -> int:
    """After everything at the top level of the user's sidebar."""
    positions = [
        CalendarMember.objects.filter(user_id=user_id, folder=None).aggregate(top=Max("position"))["top"],
        Folder.objects.filter(user_id=user_id, parent=None).aggregate(top=Max("position"))["top"],
    ]
    return max((p for p in positions if p is not None), default=-1) + 1


def sync_membership(user_id: AnyId, calendar: Calendar, *, release_direct: bool = False) -> None:
    """
    Gives the user a membership of the calendar from a group or (one they added) from its being public, or
    takes it away, as their groups and the calendar call for. A direct membership is left as it is, unless
    `release_direct` (it was just taken away): then it turns into what the user still has otherwise, keeping
    its place in the sidebar, or goes.
    """
    membership = CalendarMember.objects.filter(calendar=calendar, user_id=user_id).first()
    if membership is not None and membership.source == MembershipSource.DIRECT and not release_direct:
        return

    if CalendarGroup.objects.filter(calendar=calendar, group__user_set__id=user_id).exists():
        source = MembershipSource.GROUP
    elif membership is not None and calendar.is_public:
        # A public calendar stays in the sidebar it is in; it only gets there by being added.
        source = MembershipSource.PUBLIC
    else:
        if membership is not None:
            membership.delete()
        return

    if membership is None:
        CalendarMember.objects.create(
            calendar=calendar, user_id=user_id, source=source, role=None, position=next_sidebar_position(user_id)
        )
    elif (membership.source, membership.role) != (source, None):
        membership.source, membership.role = source, None
        membership.save(update_fields=["source", "role"])


def sync_group_link(calendar_id: AnyId) -> None:
    """After a group was given access to a calendar or the access was taken away."""
    calendar = Calendar.objects.filter(id=calendar_id).first()
    if calendar is None:
        return  # deleted along with the calendar, and its memberships with it
    users = set(User.objects.filter(groups__calendar_groups__calendar_id=calendar_id).values_list("pk", flat=True))
    users |= set(
        CalendarMember.objects.filter(calendar_id=calendar_id, source=MembershipSource.GROUP).values_list(
            "user_id", flat=True
        )
    )
    for user_id in users:
        sync_membership(user_id, calendar)


def sync_user_groups(user_id: AnyId, group_ids: Iterable[UUID] | None = None) -> None:
    """After the user joined or left groups (`group_ids`; all of their calendars of groups when None)."""
    calendar_ids = set(
        CalendarMember.objects.filter(user_id=user_id, source=MembershipSource.GROUP).values_list(
            "calendar_id", flat=True
        )
    )
    links = CalendarGroup.objects.all() if group_ids is None else CalendarGroup.objects.filter(group_id__in=group_ids)
    calendar_ids |= set(links.values_list("calendar_id", flat=True))
    for calendar in Calendar.objects.filter(id__in=calendar_ids):
        sync_membership(user_id, calendar)


def sync_public(calendar: Calendar) -> None:
    """After the calendar was made private: those who had added it lose it (its public role needs no step)."""
    if calendar.is_public:
        return
    # Deleting a queryset still sends post_delete for each row, which updates the users' sidebars.
    CalendarMember.objects.filter(calendar=calendar, source=MembershipSource.PUBLIC).delete()
