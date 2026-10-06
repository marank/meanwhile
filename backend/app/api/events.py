from datetime import datetime
from typing import List, Union

import uuid_utils
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Category, Event, EventParticipant, EventStatus, Resource, Role, User
from app.schemas import (
    EventCreate,
    EventOut,
    EventParticipantCreate,
    EventParticipantInvite,
    EventParticipantOut,
    EventParticipantUpdate,
    EventUpdate,
    OccurrenceOut,
)
from app.services.bookings import (
    can_modify_event,
    find_conflicting_approved_bookings,
    get_resource_approvers,
    initial_booking_status,
)
from app.services.activity import record_activity
from app.services.ical import serialize_event_ical
from app.services.notifications import notify
from app.services.permissions import (
    get_membership,
    get_visible_event,
    has_at_least_role,
    require_membership,
)
from app.services.recurrence import expand_events, make_aware, recurrence_count

router = APIRouter(prefix="/calendars", tags=["events"])


def _serialize_event(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        calendar_id=event.calendar_id,
        creator_id=event.creator_id,
        creator_name=event.creator_name,
        creator_email=event.creator_email,
        title=event.title,
        description=event.description,
        start=make_aware(event.start),
        end=make_aware(event.end),
        all_day=event.all_day,
        show_recurrence_count=event.show_recurrence_count,
        rrule=event.rrule,
        uid=event.uid,
        category_id=event.category_id,
        category_name=event.category.name if event.category else None,
        category_color=event.category.color if event.category else None,
        resource_id=event.resource_id,
        resource_name=event.resource.name if event.resource else None,
        status=event.status,
        decided_by=event.decided_by,
        decided_at=event.decided_at,
        decision_note=event.decision_note,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@router.get("/{calendar_id}/events", response_model=List[OccurrenceOut])
def list_events(
    calendar_id: str,
    start: datetime,
    end: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[OccurrenceOut]:
    membership = require_membership(db, calendar_id, current_user.id)
    range_start = make_aware(start)
    range_end = make_aware(end)
    if range_start >= range_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end must be after start",
        )

    events = (
        db.query(Event)
        .filter(
            Event.calendar_id == calendar_id,
            Event.start < range_end,
            # All-day ends are inclusive (expanded +1 day), so let
            # expand_events do the precise overlap check for them.
            or_(
                Event.rrule.isnot(None),
                Event.all_day.is_(True),
                Event.end > range_start,
            ),
        )
        .options(
            joinedload(Event.calendar),
            joinedload(Event.category),
            joinedload(Event.resource),
        )
        .all()
    )

    hidden_statuses = {EventStatus.REJECTED.value, EventStatus.CANCELLED.value}
    out = []
    for event, occ_start, occ_end in expand_events(events, range_start, range_end):
        if event.status in hidden_statuses and event.creator_id != current_user.id:
            continue
        out.append(
            OccurrenceOut(
                event_id=event.id,
                title=event.title,
                description=event.description,
                start=occ_start,
                end=occ_end,
                all_day=event.all_day,
                recurrence_count=(
                    recurrence_count(event, occ_start)
                    if event.show_recurrence_count and event.rrule
                    else None
                ),
                status=event.status,
                color=event.calendar.color,
                dark_color=event.calendar.dark_color,
                category_id=event.category_id,
                category_name=event.category.name if event.category else None,
                category_color=event.category.color if event.category else None,
                resource_id=event.resource_id,
                resource_name=event.resource.name if event.resource else None,
                creator_id=event.creator_id,
                can_edit=can_modify_event(
                    event, current_user.id, Role(membership.role)
                ),
                is_recurring=bool(event.rrule),
            )
        )
    out.sort(key=lambda x: x.start)
    return out


@router.post("/{calendar_id}/events", response_model=EventOut, status_code=201)
def create_event(
    calendar_id: str,
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventOut:
    membership = require_membership(db, calendar_id, current_user.id)
    if not has_at_least_role(membership, Role.CONTRIBUTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create events",
        )

    if membership.calendar.force_all_day and not data.all_day:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This calendar only allows all-day events",
        )

    start = make_aware(data.start)
    end = make_aware(data.end)
    if end < start or (end == start and not data.all_day):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end must not precede start for all-day events and must be after start otherwise",
        )

    category = None
    if data.category_id:
        category = db.query(Category).filter(
            Category.id == data.category_id,
            Category.calendar_id == calendar_id,
        ).first()
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")

    resource = None
    if data.resource_id:
        resource = (
            db.query(Resource)
            .filter(
                Resource.id == data.resource_id,
                Resource.calendar_id == calendar_id,
            )
            .first()
        )
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

    event_id = str(uuid_utils.uuid7())
    event = Event(
        id=event_id,
        calendar_id=calendar_id,
        creator_id=current_user.id,
        title=data.title if data.title is not None else '',
        description=data.description,
        start=start,
        end=end,
        all_day=data.all_day,
        show_recurrence_count=data.show_recurrence_count,
        rrule=data.rrule,
        category_id=data.category_id,
        resource_id=data.resource_id,
        uid=event_id,
        status=initial_booking_status(resource),
    )
    db.add(event)
    db.flush()

    if resource:
        conflicts = find_conflicting_approved_bookings(db, resource, event)
        if conflicts:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "This booking conflicts with an approved booking",
                    "conflicts": [c.id for c in conflicts],
                },
            )

    event.raw_ical = serialize_event_ical(event)
    record_activity(db, event, current_user.id, "created")
    if data.participants:
        for invite in data.participants:
            _create_participant(db, event, current_user, invite)
    if event.status == EventStatus.PENDING.value and resource is not None:
        notify(
            db,
            [a.id for a in get_resource_approvers(db, resource)]
            + [membership.calendar.owner_id],
            "approval_requested",
            current_user.id,
            event.title,
            calendar_id=calendar_id,
            event_id=event.id,
        )
    db.commit()
    db.refresh(event)
    return _serialize_event(event)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventOut:
    event, _ = get_visible_event(db, event_id, current_user)
    return _serialize_event(event)


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    event_id: str,
    data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventOut:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_membership(db, event.calendar_id, current_user.id)
    if not can_modify_event(event, current_user.id, Role(membership.role)):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to edit this event",
        )
    if membership.calendar.force_all_day and data.all_day is False:
        raise HTTPException(
            status_code=422,
            detail="This calendar only allows all-day events",
        )

    old_status = event.status
    old_values = {
        "title": event.title,
        "description": event.description,
        "start": make_aware(event.start),
        "end": make_aware(event.end),
        "all_day": event.all_day,
        "rrule": event.rrule,
        "category": event.category_id,
        "resource": event.resource_id,
        "show_recurrence_count": event.show_recurrence_count,
    }

    start = make_aware(data.start) if data.start else make_aware(event.start)
    end = make_aware(data.end) if data.end else make_aware(event.end)
    all_day = data.all_day if data.all_day is not None else event.all_day
    if data.start is not None or data.end is not None or data.all_day is not None:
        if end < start or (end == start and not all_day):
            raise HTTPException(
                status_code=422,
                detail="end must not precede start for all-day events and must be after start otherwise",
            )

    category = event.category
    if "category_id" in data.model_fields_set:
        if data.category_id is None:
            category = None
        else:
            category = db.query(Category).filter(
                Category.id == data.category_id,
                Category.calendar_id == event.calendar_id,
            ).first()
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found")

    resource_changed = "resource_id" in data.model_fields_set
    resource = event.resource
    if resource_changed:
        if not data.resource_id:
            resource = None
        else:
            resource = (
                db.query(Resource)
                .filter(
                    Resource.id == data.resource_id,
                    Resource.calendar_id == event.calendar_id,
                )
                .first()
            )
            if resource is None:
                raise HTTPException(
                    status_code=404, detail="Resource not found"
                )

    if "title" in data.model_fields_set:
        event.title = data.title or ''
    if "description" in data.model_fields_set:
        event.description = data.description
    if data.start is not None:
        event.start = start
    if data.end is not None:
        event.end = end
    if data.all_day is not None:
        event.all_day = data.all_day
    if data.show_recurrence_count is not None:
        event.show_recurrence_count = data.show_recurrence_count
    if "rrule" in data.model_fields_set:
        event.rrule = data.rrule
    if "category_id" in data.model_fields_set:
        event.category_id = category.id if category else None

    rescheduled = (
        data.start is not None
        or data.end is not None
        or data.all_day is not None
        or "rrule" in data.model_fields_set
    )

    if resource_changed:
        event.resource_id = resource.id if resource else None
        event.status = initial_booking_status(resource)
        event.decided_by = None
        event.decided_at = None
        event.decision_note = None
    elif (
        rescheduled
        and resource is not None
        and resource.requires_approval
        and event.status
        in {EventStatus.APPROVED.value, EventStatus.CONFIRMED.value}
    ):
        # Rescheduling an approved booking requires a fresh approval.
        event.status = EventStatus.PENDING.value
        event.decided_by = None
        event.decided_at = None
        event.decision_note = None

    if resource:
        conflicts = find_conflicting_approved_bookings(db, resource, event)
        if conflicts:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This booking conflicts with an approved booking",
                    "conflicts": [c.id for c in conflicts],
                },
            )

    changed = []
    for field, attr in (
        ("title", "title"),
        ("description", "description"),
        ("start", "start"),
        ("end", "end"),
        ("all_day", "all_day"),
        ("rrule", "rrule"),
        ("category", "category_id"),
        ("resource", "resource_id"),
        ("show_recurrence_count", "show_recurrence_count"),
    ):
        value = getattr(event, attr)
        if attr in ("start", "end"):
            value = make_aware(value)
        if value != old_values[field]:
            changed.append(field)

    event.raw_ical = serialize_event_ical(event)
    status_reset = (
        event.status == EventStatus.PENDING.value
        and old_status != EventStatus.PENDING.value
    )
    if changed:
        details = {"fields": changed}
        if status_reset:
            details["status"] = "pending"
        record_activity(db, event, current_user.id, "updated", details)
    if status_reset and resource is not None:
        notify(
            db,
            [a.id for a in get_resource_approvers(db, resource)]
            + [membership.calendar.owner_id],
            "approval_requested",
            current_user.id,
            event.title,
            calendar_id=event.calendar_id,
            event_id=event.id,
        )
    db.commit()
    db.refresh(event)
    return _serialize_event(event)


PARTICIPANT_STATUSES = {"needs_action", "accepted", "declined", "tentative"}


def _serialize_participant(participant: EventParticipant) -> EventParticipantOut:
    return EventParticipantOut(
        id=participant.id,
        event_id=participant.event_id,
        user_id=participant.user_id,
        email=participant.email,
        display_name=participant.user.display_name if participant.user else None,
        status=participant.status,
        created_at=participant.created_at,
        updated_at=participant.updated_at,
    )


def _participant_event(db: Session, event_id: str, current_user: User):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_membership(db, event.calendar_id, current_user.id)
    if not has_at_least_role(membership, Role.VIEWER):
        raise HTTPException(status_code=403, detail="You cannot view this event")
    return event, membership


def _create_participant(
    db: Session,
    event: Event,
    current_user: User,
    data: Union[EventParticipantCreate, EventParticipantInvite],
) -> EventParticipant:
    participant_status = data.status or "needs_action"
    if participant_status not in PARTICIPANT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid participant status")
    if data.user_id is not None:
        user = db.query(User).filter(User.id == data.user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        email = user.email.lower()
    else:
        email = str(data.email).lower()
        user = db.query(User).filter(User.email == email).first()
    duplicate_conditions = [EventParticipant.email == email]
    if user is not None:
        duplicate_conditions.append(EventParticipant.user_id == user.id)
    duplicate = db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        or_(*duplicate_conditions),
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Participant already exists")
    participant = EventParticipant(
        event_id=event.id, user_id=user.id if user else None, email=email, status=participant_status
    )
    db.add(participant)
    db.flush()
    if user:
        notify(
            db,
            [user.id],
            "participant_added",
            current_user.id,
            event.title or "Untitled event",
            calendar_id=event.calendar_id,
            event_id=event.id,
            data={"email": email},
        )
    return participant


@router.get("/events/{event_id}/participants", response_model=List[EventParticipantOut])
def list_event_participants(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EventParticipantOut]:
    event, _ = _participant_event(db, event_id, current_user)
    participants = (
        db.query(EventParticipant)
        .options(joinedload(EventParticipant.user))
        .filter(EventParticipant.event_id == event.id)
        .order_by(EventParticipant.created_at)
        .all()
    )
    return [_serialize_participant(participant) for participant in participants]


@router.post(
    "/events/{event_id}/participants",
    response_model=EventParticipantOut,
    status_code=201,
)
def add_event_participant(
    event_id: str,
    data: EventParticipantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventParticipantOut:
    event, membership = _participant_event(db, event_id, current_user)
    if not can_modify_event(event, current_user.id, Role(membership.role)):
        raise HTTPException(status_code=403, detail="You cannot modify this event")
    participant = _create_participant(db, event, current_user, data)
    db.commit()
    db.refresh(participant)
    return _serialize_participant(participant)


@router.patch("/events/{event_id}/participants/{participant_id}", response_model=EventParticipantOut)
def update_event_participant(
    event_id: str,
    participant_id: str,
    data: EventParticipantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventParticipantOut:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    participant = db.query(EventParticipant).filter_by(id=participant_id, event_id=event.id).first()
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    membership = get_membership(db, event.calendar_id, current_user.id)
    can_modify = membership is not None and can_modify_event(
        event, current_user.id, Role(membership.role)
    )
    if not (can_modify or participant.user_id == current_user.id):
        raise HTTPException(status_code=403, detail="You cannot update this participant")
    if data.status is None or data.status not in PARTICIPANT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid participant status")
    participant.status = data.status
    db.commit()
    db.refresh(participant)
    return _serialize_participant(participant)


@router.delete("/events/{event_id}/participants/{participant_id}", status_code=204)
def delete_event_participant(
    event_id: str,
    participant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    participant = db.query(EventParticipant).filter_by(id=participant_id, event_id=event.id).first()
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    membership = get_membership(db, event.calendar_id, current_user.id)
    can_modify = membership is not None and can_modify_event(
        event, current_user.id, Role(membership.role)
    )
    if not (can_modify or participant.user_id == current_user.id):
        raise HTTPException(status_code=403, detail="You cannot remove this participant")
    db.delete(participant)
    db.commit()


@router.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_membership(db, event.calendar_id, current_user.id)
    if not can_modify_event(event, current_user.id, Role(membership.role)):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this event",
        )
    db.delete(event)
    db.commit()
