"""
Availability: when people and resources are taken, without saying by what.
"""

from datetime import datetime

from django.db.models import Q

from core.models import Event, EventParticipant, Resource, User
from core.models.base import EventStatus, ParticipantStatus
from core.services.recurrence import expand_events

_TAKEN = {EventStatus.CONFIRMED, EventStatus.APPROVED}


def _overlapping(events, start: datetime, end: datetime):
    return events.filter(
        Q(start__lt=end),
        Q(rrule__isnull=False) | ~Q(rdates=[]) | Q(all_day=True) | Q(end__gt=start),
    )


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for begin, finish in sorted(intervals):
        if merged and begin <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], finish))
        else:
            merged.append((begin, finish))
    return merged


def _periods(occurrences, start: datetime, end: datetime, tentative) -> list[dict]:
    """Busy and tentative periods, each merged; a busy time hides a tentative one at the same time."""
    busy: list[tuple[datetime, datetime]] = []
    maybe: list[tuple[datetime, datetime]] = []
    for event, begin, finish in occurrences:
        period = (max(begin, start), min(finish, end))
        (maybe if tentative(event) else busy).append(period)
    busy = _merge(busy)
    result = [{"start": b, "end": f, "tentative": False} for b, f in busy]
    for b, f in _merge(maybe):
        if not any(b >= bb and f <= ff for bb, ff in busy):
            result.append({"start": b, "end": f, "tentative": True})
    return sorted(result, key=lambda p: p["start"])


def _without(events, exclude_event_id: str | None):
    # The event being planned doesn't block itself, nor do its changed occurrences.
    if exclude_event_id:
        events = events.exclude(Q(pk=exclude_event_id) | Q(parent_id=exclude_event_id))
    return events


def user_periods(user: User, start: datetime, end: datetime, exclude_event_id: str | None = None) -> list[dict]:
    """When the user is taken: by events they created or take part in (declined ones aside).

    Pending bookings and invitations not yet accepted count as tentative.
    """
    attending = Q(participants__user=user) | Q(participants__email__iexact=user.email)
    events = _overlapping(
        Event.objects.filter(Q(creator=user) | attending)
        .exclude(status__in={EventStatus.REJECTED, EventStatus.CANCELLED})
        .distinct(),
        start,
        end,
    )
    events = _without(events, exclude_event_id)
    answers = dict(
        EventParticipant.objects.filter(Q(user=user) | Q(email__iexact=user.email)).values_list("event_id", "status")
    )
    occurrences = [
        (event, begin, finish)
        for event, begin, finish in expand_events(events, start, end)
        if answers.get(event.id) != ParticipantStatus.DECLINED
    ]

    unsure = {ParticipantStatus.NEEDS_ACTION, ParticipantStatus.TENTATIVE}

    def tentative(event: Event) -> bool:
        return event.status == EventStatus.PENDING or answers.get(event.id) in unsure

    return _periods(occurrences, start, end, tentative)


def resource_periods(
    resource: Resource, start: datetime, end: datetime, exclude_event_id: str | None = None
) -> list[dict]:
    """When the resource is booked; bookings awaiting approval count as tentative."""
    events = _overlapping(
        Event.objects.filter(
            Q(resource=resource) | Q(location_resource=resource), status__in=_TAKEN | {EventStatus.PENDING}
        ),
        start,
        end,
    )
    events = _without(events, exclude_event_id)
    return _periods(expand_events(events, start, end), start, end, lambda e: e.status == EventStatus.PENDING)
