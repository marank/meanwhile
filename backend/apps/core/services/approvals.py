"""
Deciding on bookings: approving, rejecting and cancelling events, with what follows (changed occurrences,
iTIP messages to participants, the activity log and notifications).
"""

from django.db import transaction
from django.utils import timezone
from ninja.errors import HttpError

from apps.core.models import Event, User
from apps.core.models.base import EventStatus
from apps.core.services.activity import record_activity
from apps.core.services.bookings import (
    approvers_of,
    booked_resources,
    decidable_resources,
    find_booking_conflicts,
    is_in_approver_pool,
)
from apps.core.services.itip import send_cancel, send_request
from apps.core.services.notifications import notify
from apps.core.services.permissions import can_modify_event, get_membership


def _locked_event(event_id: str) -> Event:
    # Locked, so approvers deciding at once each see the others' decisions (awaiting_approval).
    return Event.objects.select_for_update().get(id=event_id)


def _require_no_conflicts(event: Event) -> None:
    conflicts = find_booking_conflicts(event)
    # Changed occurrences waiting along with the series are approved with it.
    for occurrence in event.overrides.filter(status=event.status):
        conflicts += find_booking_conflicts(occurrence)
    if conflicts:
        raise HttpError(
            409,
            # Structured, which apps.core.api.http_error passes through; Ninja types the message as a str.
            {  # type: ignore[arg-type]
                "message": "Approval conflicts with an existing approved booking",
                "conflicts": [str(c.id) for c in conflicts],
            },
        )


def _notify_creator(event: Event, kind: str, user: User, note: str) -> None:
    notify(
        [str(event.creator_id)],
        kind,
        str(user.id),
        event.title,
        calendar_id=str(event.calendar_id),
        event_id=str(event.id),
        data={"note": note} if note else None,
    )


@transaction.atomic
def approve(event_id: str, user: User, note: str) -> Event:
    """Approves the bookings of the event that `user` is responsible for (e.g. the room or the
    projector); the event is approved once none is left."""
    event = _locked_event(event_id)
    if event.status != EventStatus.PENDING:
        raise HttpError(400, "Event is not pending")
    if get_membership(event.calendar, user) is None:
        raise HttpError(403, "Not a member of this calendar")
    decided = decidable_resources(event, str(user.id))
    if not decided:
        raise HttpError(403, "You cannot approve this booking")
    decided_ids = {str(r.pk) for r in decided}
    remaining = [i for i in event.awaiting_approval or [] if str(i) not in decided_ids]
    if not remaining:
        _require_no_conflicts(event)

    previous_status = event.status
    event.awaiting_approval = remaining
    event.decided_by = user
    event.decided_at = timezone.now()
    event.decision_note = note
    if not remaining:
        event.status = EventStatus.APPROVED
    event.save()
    _decide_changed_occurrences(event, previous_status, decided_ids)
    details: dict[str, list[str] | str] = {"resources": sorted(r.name for r in decided)}
    if note:
        details["note"] = note
    record_activity(event, str(user.id), "approved", details)
    if not remaining:
        # Participants were invited to a tentative event; now it takes place.
        send_request(event, update=True)
        _notify_creator(event, "booking_approved", user, note)
    return event


def _decide_changed_occurrences(series: Event, previous_status: str, decided_ids: set[str] | None = None) -> None:
    # Changed occurrences that shared the series' status follow its decision.
    for occurrence in series.overrides.filter(status=previous_status):
        awaiting = [
            i for i in occurrence.awaiting_approval or [] if decided_ids is not None and str(i) not in decided_ids
        ]
        if decided_ids is not None and awaiting:
            occurrence.awaiting_approval = awaiting
        else:
            occurrence.status = series.status if decided_ids is None else EventStatus.APPROVED
            occurrence.awaiting_approval = []
        occurrence.decided_by = series.decided_by
        occurrence.decided_at = series.decided_at
        occurrence.decision_note = series.decision_note
        occurrence.save()


@transaction.atomic
def reject(event_id: str, user: User, note: str) -> Event:
    event = _locked_event(event_id)
    if event.status != EventStatus.PENDING:
        raise HttpError(400, "Event is not pending")
    if get_membership(event.calendar, user) is None:
        raise HttpError(403, "Not a member of this calendar")
    if not is_in_approver_pool(event, user.id):
        raise HttpError(403, "You cannot reject this booking")

    previous_status = event.status
    event.status = EventStatus.REJECTED
    event.awaiting_approval = []
    event.decided_by = user
    event.decided_at = timezone.now()
    event.decision_note = note
    event.save()
    _decide_changed_occurrences(event, previous_status)
    send_cancel(event)
    record_activity(event, str(user.id), "rejected", {"note": note} if note else None)
    _notify_creator(event, "booking_rejected", user, note)
    return event


@transaction.atomic
def cancel(event_id: str, user: User) -> Event:
    event = _locked_event(event_id)
    membership = get_membership(event.calendar, user)
    if membership is None:
        raise HttpError(403, "Not a member of this calendar")
    if not can_modify_event(event, user.id, membership.role):
        raise HttpError(403, "You cannot cancel this event")

    had_booking = event.status in {EventStatus.PENDING, EventStatus.APPROVED} and bool(booked_resources(event))
    previous_status = event.status
    event.status = EventStatus.CANCELLED
    event.awaiting_approval = []
    event.decided_by = user
    event.decided_at = timezone.now()
    event.save()
    _decide_changed_occurrences(event, previous_status)
    send_cancel(event)
    record_activity(event, str(user.id), "cancelled")
    if had_booking:
        # Who decides on the bookings and the calendar's owner.
        recipients = [str(a.id) for a in approvers_of(booked_resources(event))]
        recipients.append(str(event.calendar.owner_id))
        notify(
            recipients,
            "booking_cancelled",
            str(user.id),
            event.title,
            calendar_id=str(event.calendar_id),
            event_id=str(event.id),
        )
    return event
