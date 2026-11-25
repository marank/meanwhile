"""
Changing single occurrences of recurring events.

A series keeps the starts of removed occurrences in `exdates`; a changed occurrence is an event of
its own with the series as parent and the original start as recurrence_id.
"""

import copy
from collections.abc import Callable
from datetime import datetime, timedelta

from apps.core.models import Event, EventParticipant
from apps.core.services.recurrence import (
    as_utc,
    format_exdate,
    format_rrule,
    is_series,
    nth_occurrence,
    occurrence_index,
    parse_exdates,
    rrule_parts,
)


def snapshot(event: Event) -> Event:
    """A copy of the event as it is now, to compare against after a change."""
    return copy.copy(event)


def is_occurrence(series: Event, start: datetime) -> bool:
    """Whether the series has an occurrence starting then that hasn't been removed."""
    start = as_utc(start)
    if series.overrides.filter(recurrence_id=start).exists():
        return True
    return start not in parse_exdates(series.exdates) and occurrence_index(series, start) is not None


def override_for(series: Event, start: datetime) -> Event:
    """The changed occurrence starting at `start`, created as a copy of the series if needed."""
    start = as_utc(start)
    override = series.overrides.filter(recurrence_id=start).first()
    if override is not None:
        return override
    duration = series.end - series.start
    override = Event(
        calendar=series.calendar,
        # The occurrence belongs to whoever owns the series, so the same people may change it.
        creator=series.creator,
        parent=series,
        recurrence_id=start,
        uid=series.uid,
        title=series.title,
        description=series.description,
        start=start,
        end=start + duration,
        all_day=series.all_day,
        timezone=series.timezone,
        category=series.category,
        resource=series.resource,
        location=series.location,
        location_resource=series.location_resource,
        show_as=series.show_as,
        awaiting_approval=list(series.awaiting_approval or []),
        status=series.status,
        decided_by=series.decided_by,
        decided_at=series.decided_at,
        decision_note=series.decision_note,
    )
    override.save()
    # The occurrence starts out with the series' participants and can then differ.
    for participant in series.participants.all():
        EventParticipant.objects.create(
            event=override, user=participant.user, email=participant.email, status=participant.status
        )
    return override


def remove_occurrence(series: Event, start: datetime) -> None:
    start = as_utc(start)
    series.overrides.filter(recurrence_id=start).delete()
    exdates = parse_exdates(series.exdates) | {start}
    series.exdates = sorted(format_exdate(d) for d in exdates)
    series.save()


def end_before(series: Event, start: datetime) -> None:
    """Ends the series with the last occurrence before `start`; later exceptions are dropped."""
    start = as_utc(start)
    if series.rrule:
        parts = rrule_parts(series.rrule)
        parts.pop("COUNT", None)
        if series.all_day:
            parts["UNTIL"] = (start - timedelta(days=1)).strftime("%Y%m%d")
        else:
            parts["UNTIL"] = (start - timedelta(seconds=1)).strftime("%Y%m%dT%H%M%SZ")
        series.rrule = format_rrule(parts)
    series.rdates = sorted(format_exdate(d) for d in parse_exdates(series.rdates) if d < start)
    series.exdates = sorted(format_exdate(d) for d in parse_exdates(series.exdates) if d < start)
    series.save()
    series.overrides.filter(recurrence_id__gte=start).delete()


def split(series: Event, start: datetime) -> Event:
    """Ends the series before `start` and continues it as a new series from there on.

    The occurrences changed or removed from `start` on move to the new series.
    """
    start = as_utc(start)
    index = occurrence_index(series, start)
    # Callers split only at an occurrence after the first.
    assert index is not None
    rrule = None
    if series.rrule:
        parts = rrule_parts(series.rrule)
        if "COUNT" in parts:
            # COUNT includes the extra dates (RDATE) before `start`; good enough for the rare mix of both.
            parts["COUNT"] = str(max(1, int(parts["COUNT"]) - index))
        rrule = format_rrule(parts)
    duration = series.end - series.start
    later_exdates = [d for d in parse_exdates(series.exdates) if d >= start]
    later_overrides = list(series.overrides.filter(recurrence_id__gte=start))

    following = Event(
        calendar=series.calendar,
        creator=series.creator,
        title=series.title,
        description=series.description,
        start=start,
        end=start + duration,
        all_day=series.all_day,
        timezone=series.timezone,
        show_recurrence_count=series.show_recurrence_count,
        rrule=rrule,
        rdates=sorted(format_exdate(d) for d in parse_exdates(series.rdates) if d > start),
        exdates=sorted(format_exdate(d) for d in later_exdates),
        category=series.category,
        resource=series.resource,
        location=series.location,
        location_resource=series.location_resource,
        show_as=series.show_as,
        awaiting_approval=list(series.awaiting_approval or []),
        status=series.status,
        decided_by=series.decided_by,
        decided_at=series.decided_at,
        decision_note=series.decision_note,
    )
    following.uid = str(following.id)

    following.save()
    # Move the later occurrences over before ending the series, which would delete them.
    for override in later_overrides:
        override.parent = following
        override.uid = following.uid
        override.save()
    end_before(series, start)
    for participant in series.participants.all():
        EventParticipant.objects.create(
            event=following, user=participant.user, email=participant.email, status=participant.status
        )
    return following


def remap_exceptions(series: Event, before: Event) -> None:
    """Keeps removed and changed occurrences attached after the series was rescheduled.

    With the same rule, the n-th occurrence stays the n-th one (e.g. all moved by an hour);
    with another rule, exceptions are kept only where the new series still has an occurrence.
    """
    if not is_series(series):
        series.exdates = []
        series.overrides.all().delete()
        return
    unchanged = (
        before.rrule == series.rrule
        and before.rdates == series.rdates
        and before.start == series.start
        and before.all_day == series.all_day
        and before.timezone == series.timezone
    )
    if unchanged:
        return
    moved = _occurrence_mover(series, before)
    series.exdates = sorted(format_exdate(new) for d in parse_exdates(series.exdates) if (new := moved(d)) is not None)
    _move_overrides(series, moved)


def _occurrence_mover(series: Event, before: Event) -> Callable[[datetime], datetime | None]:
    """Where an occurrence of the series as it was `before` is now (None: it's gone)."""
    same_rule = (
        before.rrule == series.rrule
        and len(before.rdates or []) == len(series.rdates or [])
        and before.all_day == series.all_day
    )

    def by_position(start: datetime) -> datetime | None:
        index = occurrence_index(before, start)
        return nth_occurrence(series, index) if index is not None else None

    def if_still_there(start: datetime) -> datetime | None:
        return start if occurrence_index(series, start) is not None else None

    return by_position if same_rule and is_series(before) else if_still_there


def _move_overrides(series: Event, moved: Callable[[datetime], datetime | None]) -> None:
    """Gives the changed occurrences their new start; those whose occurrence is gone are deleted."""
    overrides = list(series.overrides.all())
    targets = {}
    for override in overrides:
        # Overrides always keep the start of the occurrence they replace.
        assert override.recurrence_id is not None
        targets[override.pk] = moved(override.recurrence_id)
    # Clear the old ids first so that two occurrences can trade places without a clash.
    Event.objects.filter(pk__in=[o.pk for o in overrides]).update(recurrence_id=None)
    for override in overrides:
        target = targets[override.pk]
        if target is None:
            override.delete()
        else:
            override.recurrence_id = target
            override.save()
