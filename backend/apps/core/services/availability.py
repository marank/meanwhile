"""
Availability: when people and resources are taken, without saying by what.
"""

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from django.db.models import Q, QuerySet

from apps.core.models import Event, EventParticipant, Resource, User
from apps.core.models.base import FREE_TIME, EventStatus, ParticipantStatus, ShowAs
from apps.core.services.recurrence import expand_events

_TAKEN = {EventStatus.CONFIRMED, EventStatus.APPROVED}


def _overlapping(events: QuerySet[Event], start: datetime, end: datetime) -> QuerySet[Event]:
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


def _periods(
    occurrences: Iterable[tuple[Event, datetime, datetime]],
    start: datetime,
    end: datetime,
    tentative: Callable[[Event], bool],
    away: Callable[[Event], bool] = lambda _event: False,
) -> list[dict[str, Any]]:
    """Out-of-office, busy and tentative periods, each merged; a time of the kinds before hides one of
    the kinds after it within it."""
    kinds: dict[str, list[tuple[datetime, datetime]]] = {"away": [], "busy": [], "maybe": []}
    for event, begin, finish in occurrences:
        kind = "away" if away(event) else "maybe" if tentative(event) else "busy"
        kinds[kind].append((max(begin, start), min(finish, end)))
    result: list[dict[str, Any]] = []
    shown: list[tuple[datetime, datetime]] = []
    for kind, intervals in kinds.items():
        merged = [(b, f) for b, f in _merge(intervals) if not any(b >= sb and f <= sf for sb, sf in shown)]
        result += [
            {"start": b, "end": f, "tentative": kind == "maybe", "out_of_office": kind == "away"} for b, f in merged
        ]
        shown += merged
    return sorted(result, key=lambda p: p["start"])


def _without(events: QuerySet[Event], exclude_event_id: str | None) -> QuerySet[Event]:
    # The event being planned doesn't block itself, nor do its changed occurrences.
    if exclude_event_id:
        events = events.exclude(Q(pk=exclude_event_id) | Q(parent_id=exclude_event_id))
    return events


def user_periods(
    user: User, start: datetime, end: datetime, exclude_event_id: str | None = None
) -> list[dict[str, Any]]:
    """When the user is taken: by events they created or take part in (declined ones aside), unless
    those are shown as free or "working elsewhere".

    Pending bookings, invitations not yet accepted and events shown as tentative count as tentative.
    """
    attending = Q(participants__user=user) | Q(participants__email__iexact=user.email)
    events = _overlapping(
        Event.objects.filter(Q(creator=user) | attending)
        .exclude(status__in={EventStatus.REJECTED, EventStatus.CANCELLED})
        .exclude(show_as__in=FREE_TIME)
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
        return (
            event.status == EventStatus.PENDING or event.show_as == ShowAs.TENTATIVE or answers.get(event.id) in unsure
        )

    def away(event: Event) -> bool:
        # Who hasn't said yet whether they come isn't away because of it.
        return event.show_as == ShowAs.OUT_OF_OFFICE and not tentative(event)

    return _periods(occurrences, start, end, tentative, away)


def resource_periods(
    resource: Resource, start: datetime, end: datetime, exclude_event_id: str | None = None
) -> list[dict[str, Any]]:
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
