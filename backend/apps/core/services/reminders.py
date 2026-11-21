"""
Event reminders: each user's own reminders before the occurrences of events they can see.

Due reminders become in-app notifications, delivered by a regular job (apps.core.tasks). Each reminder
knows when it is next due, so that a delivery only looks at those due by then; a change of the event
(or the user's zone) has it work that out again.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import Event, EventReminder, ReminderDelivery, User
from apps.core.models.base import EventStatus
from apps.core.realtime import broadcast
from apps.core.services.notifications import notify
from apps.core.services.permissions import can_see_event, get_membership
from apps.core.services.recurrence import as_utc, expand_event, is_series, occurrence_starts, zone

# Reminders found late (e.g. while the app was closed) still go out until this long after the start.
LATE_DELIVERY = timedelta(minutes=15)
# Choices the app offers; clients may store other values via CalDAV, within these bounds.
MAX_MINUTES_BEFORE = 4 * 7 * 24 * 60
# Per user and event: every one is worked out again at each delivery (deliver_due_reminders).
MAX_REMINDERS = 10

_HIDDEN = {EventStatus.REJECTED, EventStatus.CANCELLED}


def series_of(event: Event) -> Event:
    """Reminders belong to the series; a changed occurrence is reminded of like the others."""
    return event.parent or event


def reminder_minutes(event: Event, user: User) -> list[int]:
    return sorted(
        EventReminder.objects.filter(event=series_of(event), user=user).values_list("minutes_before", flat=True)
    )


def allowed_minutes(minutes: Iterable[int]) -> list[int]:
    """The reminders kept of those asked for, by the app or as CalDAV alarms: within
    MAX_MINUTES_BEFORE, each once, and the MAX_REMINDERS closest to the start."""
    return sorted({m for m in minutes if 0 <= m <= MAX_MINUTES_BEFORE})[:MAX_REMINDERS]


def set_reminders(event: Event, user: User, minutes: list[int]) -> list[int]:
    series = series_of(event)
    wanted = allowed_minutes(minutes)
    with transaction.atomic():
        EventReminder.objects.filter(event=series, user=user).exclude(minutes_before__in=wanted).delete()
        for before in wanted:
            EventReminder.objects.get_or_create(event=series, user=user, minutes_before=before)
        # The user's CalDAV clients show the reminders as alarms and must fetch the event again.
        Event.objects.filter(pk=series.pk).update(updated_at=timezone.now())
    return wanted


def _local_start(event: Event, start: datetime, user: User) -> datetime:
    # All-day occurrences begin at midnight where the user is, not at midnight UTC.
    if event.all_day:
        local = zone(user.timezone or "UTC")
        return datetime.combine(start.date(), datetime.min.time(), tzinfo=local).astimezone(UTC)
    return start


def _occurrences(series: Event, user: User, after: datetime, before: datetime) -> list[tuple[Event, datetime]]:
    """(event, start) of the series' occurrences starting in (after, before], changed ones included."""
    # All-day starts move by up to a day with the user's zone; look a day further each way.
    window = expand_event(series, after - timedelta(days=1), before + timedelta(days=1))
    found = [(series, _local_start(series, start, user)) for start, _ in window]
    if is_series(series):
        found += [
            (override, _local_start(override, as_utc(override.start), user)) for override in series.overrides.all()
        ]
    return [(event, start) for event, start in found if after < start <= before]


# Deliveries only guard against reminding twice; older ones are removed regularly (apps.core.tasks).
DELIVERY_RETENTION = timedelta(days=30)


def deliver_due_reminders(user: User | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Turns due reminders into notifications, which pop up in the users' open tabs; returns those
    delivered now."""
    now = now or timezone.now()
    reminders = (
        EventReminder.objects.select_related("event__calendar", "user")
        .prefetch_related("event__overrides")
        .filter(next_due_at__lte=now, event__parent__isnull=True, user__is_active=True)
    )
    if user is not None:
        reminders = reminders.filter(user=user)

    delivered: list[dict[str, Any]] = []
    by_user: dict[UUID, list[dict[str, Any]]] = {}
    for reminder in reminders:
        for reminded in _deliver(reminder, now):
            delivered.append(reminded)
            by_user.setdefault(reminder.user.id, []).append(reminded)
        reminder.next_due_at = _next_due(reminder, now)
        reminder.save(update_fields=["next_due_at"])
    for user_id, user_reminders in by_user.items():
        broadcast.reminders_due(user_id, user_reminders)
    return delivered


def _deliver(reminder: EventReminder, now: datetime) -> list[dict[str, Any]]:
    """Notifies the reminder's user of each occurrence it is due for and they can still see, once each;
    returns those reminded of."""
    series, reader = reminder.event, reminder.user
    membership = get_membership(series.calendar, reader)
    if membership is None:
        return []  # without access, nothing is due
    before = timedelta(minutes=reminder.minutes_before)
    reminded: list[dict[str, Any]] = []
    # Occurrences whose reminder time has come, and that haven't long begun.
    for event, start in _occurrences(series, reader, now - LATE_DELIVERY, now + before):
        if event.status in _HIDDEN or not can_see_event(event, reader, membership):
            continue
        if not _record_delivery(reminder, start):
            continue  # already reminded of this occurrence
        data = {"start": start.isoformat(), "all_day": event.all_day, "minutes_before": reminder.minutes_before}
        notify(
            [str(reader.id)],
            "event_reminder",
            None,
            event.title or "Untitled event",
            calendar_id=str(event.calendar_id),
            event_id=str(event.id),
            data=data,
        )
        reminded.append({"event_id": str(event.id), "title": event.title, **data})
    return reminded


def _record_delivery(reminder: EventReminder, start: datetime) -> bool:
    """Notes that the occurrence starting at `start` was reminded of; False if it already was, so that
    concurrent deliveries remind of it only once."""
    try:
        with transaction.atomic():
            ReminderDelivery.objects.create(reminder=reminder, occurrence_start=start)
    except IntegrityError:
        return False
    return True


def _next_due(reminder: EventReminder, now: datetime) -> datetime | None:
    """When the reminder is due after a delivery at `now`: for the first occurrence that delivery
    didn't cover, the first starting more than its minutes before from now."""
    series, user = reminder.event, reminder.user
    if series.status in _HIDDEN:
        return None  # unless the event changes again (reminders_changed)
    before = timedelta(minutes=reminder.minutes_before)
    covered = now + before
    starts = []
    # All-day starts move by up to a day with the user's zone; look from a day earlier.
    for start in occurrence_starts(series, covered - timedelta(days=1)):
        local = _local_start(series, start, user)
        if local > covered:
            starts.append(local)
            break
    for override in series.overrides.all() if is_series(series) else []:
        local = _local_start(override, override.start, user)
        if local > covered and override.status not in _HIDDEN:
            starts.append(local)
    return min(starts) - before if starts else None


def reminders_changed(series_id: UUID | str | None = None, user_id: UUID | str | None = None) -> None:
    """The event (a series) or the user's zone changed: their reminders are worked out again by the
    next delivery."""
    reminders = EventReminder.objects.all()
    if series_id is not None:
        reminders = reminders.filter(event_id=series_id)
    if user_id is not None:
        reminders = reminders.filter(user_id=user_id)
    reminders.update(next_due_at=timezone.now())
