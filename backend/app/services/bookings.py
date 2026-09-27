from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models import CalendarApprover, Event, EventStatus, Resource, ResourceApprover, Role, User
from app.services.permissions import get_membership


def get_resource_approvers(db: Session, resource: Resource) -> List[User]:
    resource_approvers = [a.user for a in resource.approvers]
    if resource_approvers:
        return resource_approvers
    calendar_approvers = [
        a.user
        for a in db.query(CalendarApprover)
        .filter(CalendarApprover.calendar_id == resource.calendar_id)
        .all()
    ]
    if calendar_approvers:
        return calendar_approvers
    # Fallback to owner
    return [resource.calendar.owner]


def is_in_approver_pool(
    db: Session, event: Event, user: User | None = None, user_id: str | None = None
) -> bool:
    if user_id is None and user is not None:
        user_id = user.id
    if user_id is None:
        return False
    # Owner can always approve
    if event.calendar.owner_id == user_id:
        return True
    if event.resource is None:
        return False
    approvers = get_resource_approvers(db, event.resource)
    return any(a.id == user_id for a in approvers)


def initial_booking_status(resource: Resource | None) -> str:
    if resource is not None and resource.requires_approval:
        return EventStatus.PENDING.value
    return EventStatus.CONFIRMED.value


def find_conflicting_approved_bookings(
    db: Session,
    resource: Resource,
    event: Event,
) -> List[Event]:
    from app.services.recurrence import find_conflicts, make_aware

    # Serialize concurrent bookings on the same resource so two approvals
    # cannot both pass the conflict check (a no-op on SQLite).
    db.query(Resource).filter(Resource.id == resource.id).with_for_update().first()

    horizon = max(make_aware(event.end), make_aware(event.start) + timedelta(days=730))
    approved = (
        db.query(Event)
        .filter(
            Event.resource_id == resource.id,
            Event.status.in_(
                {EventStatus.APPROVED.value, EventStatus.CONFIRMED.value}
            ),
            Event.start < horizon,
        )
        .all()
    )
    return find_conflicts(event, approved, horizon)


def can_modify_event(event: Event, user_id: str, role: Role) -> bool:
    if role == Role.OWNER or role == Role.EDITOR:
        return True
    return event.creator_id == user_id
