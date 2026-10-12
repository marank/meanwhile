"""
Resource booking approval/conflict logic.
"""

from datetime import datetime, timedelta, timezone

from django.db import transaction
from django.db.models import Q

from core.models.base import EventStatus, Role
from core.models.calendars import CalendarApprover
from core.models.events import Event
from core.models.resources import Resource
from core.models.users import User
from core.services.recurrence import find_conflicts, make_aware


def get_resource_approvers(resource: Resource):
    """The resource's own approvers, else the calendar's default approvers; may be empty.

    The calendar owner can always decide regardless (see is_in_approver_pool).
    """
    resource_approvers = [a.user for a in resource.approvers.all()]
    if resource_approvers:
        return resource_approvers
    return [
        a.user
        for a in CalendarApprover.objects.filter(calendar=resource.calendar).select_related("user")
    ]


def can_decide_booking(calendar, resource: Resource | None, user_id: str) -> bool:
    """The calendar owner and the resource's approver pool may approve or reject bookings."""
    if str(calendar.owner_id) == str(user_id):
        return True
    if resource is None:
        return False
    return any(str(a.id) == str(user_id) for a in get_resource_approvers(resource))


def booked_resources(event: Event) -> list[Resource]:
    """What the event books: its location (a place) and its resource, each at most once."""
    booked = []
    for resource in (event.location_resource, event.resource):
        if resource is not None and all(r.pk != resource.pk for r in booked):
            booked.append(resource)
    return booked


def awaiting_resources(event: Event) -> list[Resource]:
    """The booked resources whose approval a pending event still waits for."""
    awaiting = {str(i) for i in event.awaiting_approval or []}
    return [r for r in booked_resources(event) if str(r.pk) in awaiting]


def is_in_approver_pool(event: Event, user: User | None = None, user_id: str | None = None) -> bool:
    """Whether the user may decide on the event's bookings: those it waits for, if it is pending."""
    if user_id is None and user is not None:
        user_id = str(user.id)
    if user_id is None:
        return False
    resources = awaiting_resources(event) if event.status == EventStatus.PENDING else booked_resources(event)
    return any(can_decide_booking(event.calendar, r, user_id) for r in resources)


def decidable_resources(event: Event, user_id: str) -> list[Resource]:
    """The bookings the event waits for that this user may approve or reject."""
    return [r for r in awaiting_resources(event) if can_decide_booking(event.calendar, r, user_id)]


def approvers_of(resources) -> list[User]:
    """Everyone who may decide on any of the resources' bookings, besides the calendar owner."""
    users: dict[str, User] = {}
    for resource in resources:
        for user in get_resource_approvers(resource):
            users.setdefault(str(user.pk), user)
    return list(users.values())


def update_booking_status(event: Event, user: User, recheck: list[Resource]) -> None:
    """Sets the event's status after its bookings changed.

    `recheck`: bookings that are new or now at another time; they need approval again unless
    the user may approve them. Other bookings keep their state.
    """
    booked = booked_resources(event)
    booked_ids = {str(r.pk) for r in booked}
    rechecked = {str(r.pk) for r in recheck}
    awaiting = [i for i in (event.awaiting_approval or []) if str(i) in booked_ids and str(i) not in rechecked]
    awaiting += [
        str(r.pk)
        for r in recheck
        if r.requires_approval and not can_decide_booking(event.calendar, r, str(user.pk))
    ]
    was_pending = event.status == EventStatus.PENDING
    event.awaiting_approval = awaiting
    if awaiting:
        event.status = EventStatus.PENDING
        event.decided_by = None
        event.decided_at = None
        event.decision_note = None
    elif any(r.requires_approval for r in booked):
        if was_pending or event.status == EventStatus.CONFIRMED or recheck:
            # Booked by someone who may approve it all: the approval step is skipped.
            event.status = EventStatus.APPROVED
            event.decided_by = user
            event.decided_at = datetime.now(timezone.utc)
    else:
        event.status = EventStatus.CONFIRMED
        event.decided_by = None
        event.decided_at = None


def find_booking_conflicts(event: Event) -> list[Event]:
    """Approved bookings of any of the event's resources at the same time."""
    conflicts = []
    for resource in booked_resources(event):
        conflicts += [c for c in find_conflicting_approved_bookings(resource, event) if c not in conflicts]
    return conflicts


def find_conflicting_approved_bookings(resource: Resource, event: Event):
    with transaction.atomic():
        # Serialize concurrent approvals on the same resource.
        Resource.objects.select_for_update().get(pk=resource.pk)

        horizon = max(make_aware(event.end), make_aware(event.start) + timedelta(days=730))
        # A series doesn't conflict with its own changed occurrences, nor they with it.
        series_id = event.parent_id or event.pk
        approved = Event.objects.filter(
            Q(resource=resource) | Q(location_resource=resource),
            status__in={EventStatus.APPROVED, EventStatus.CONFIRMED},
            start__lt=horizon,
        )
        if series_id is not None:
            approved = approved.exclude(Q(pk=series_id) | Q(parent_id=series_id))
        approved = approved.exclude(pk=event.pk)
        return find_conflicts(event, approved, horizon)


def can_modify_event(event: Event, user_id: str, role: str) -> bool:
    return role in {Role.OWNER, Role.FULL} or str(event.creator_id) == str(user_id)
