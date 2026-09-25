from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Event, EventStatus, Role, User
from app.schemas import ApprovalAction, ApprovalOut, ApproverOut
from app.services.bookings import (
    find_conflicting_approved_bookings,
    get_resource_approvers,
    is_in_approver_pool,
)
from app.services.permissions import has_at_least_role, require_membership

router = APIRouter(prefix="", tags=["approvals"])


def _serialize_approval(event: Event) -> ApprovalOut:
    approvers = [
        ApproverOut(
            user_id=a.id,
            email=a.email,
            display_name=a.display_name,
        )
        for a in get_resource_approvers(Session.object_session(event), event.resource)
    ] if event.resource else []

    return ApprovalOut(
        id=event.id,
        calendar_id=event.calendar_id,
        creator_id=event.creator_id,
        title=event.title,
        description=event.description,
        start=event.start,
        end=event.end,
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
        approver_pool=approvers,
    )


@router.get("/approvals", response_model=List[ApprovalOut])
def list_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ApprovalOut]:
    pending = (
        db.query(Event)
        .filter(
            Event.status == EventStatus.PENDING.value,
            Event.resource_id.isnot(None),
        )
        .all()
    )
    result = []
    for event in pending:
        if is_in_approver_pool(db, event, user=current_user):
            result.append(_serialize_approval(event))
    return result


@router.post("/events/{event_id}/approve")
def approve_event(
    event_id: str,
    action: ApprovalAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalOut:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != EventStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Event is not pending")
    membership = require_membership(db, event.calendar_id, current_user.id)
    if not is_in_approver_pool(db, event, user=current_user):
        raise HTTPException(status_code=403, detail="You cannot approve this booking")

    conflicts = find_conflicting_approved_bookings(db, event.resource, event)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Approval conflicts with an existing approved booking",
                "conflicts": [c.id for c in conflicts],
            },
        )

    event.status = EventStatus.APPROVED.value
    event.decided_by = current_user.id
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = action.note
    db.commit()
    db.refresh(event)
    return _serialize_approval(event)


@router.post("/events/{event_id}/reject")
def reject_event(
    event_id: str,
    action: ApprovalAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalOut:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != EventStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Event is not pending")
    require_membership(db, event.calendar_id, current_user.id)
    if not is_in_approver_pool(db, event, user=current_user):
        raise HTTPException(status_code=403, detail="You cannot reject this booking")

    event.status = EventStatus.REJECTED.value
    event.decided_by = current_user.id
    event.decided_at = datetime.now(timezone.utc)
    event.decision_note = action.note
    db.commit()
    db.refresh(event)
    return _serialize_approval(event)


@router.post("/events/{event_id}/cancel")
def cancel_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalOut:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_membership(db, event.calendar_id, current_user.id)
    if event.creator_id != current_user.id and not has_at_least_role(
        membership, Role.EDITOR
    ):
        raise HTTPException(
            status_code=403,
            detail="You cannot cancel this event",
        )

    event.status = EventStatus.CANCELLED.value
    event.decided_by = current_user.id
    event.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return _serialize_approval(event)
