"""
Event reminders: each user's own reminders before the occurrences of events they can see.

Due reminders become in-app notifications. They are delivered when the app asks for the user's
unread count (about once a minute while it is open) and by the `send_reminders` command,
which can run from cron so that reminders also go out while nobody has the app open.
"""

from datetime import datetime, timedelta, timezone

from django.db import IntegrityError, transaction
from django.db.models import Max

from core.models import Event, EventReminder, ReminderDelivery, User
from core.models.base import EventStatus
from core.services.notifications import notify
from core.services.permissions import can_see_event, get_membership
from core.services.recurrence import expand_event, is_series, make_aware, zone

# Reminders found late (e.g. while the app was closed) still go out until this long after the start.
LATE_DELIVERY = timedelta(minutes=15)
# Choices the app offers; clients may store other values via CalDAV.
MAX_MINUTES_BEFORE = 4 * 7 * 24 * 60

_HIDDEN = {EventStatus.REJECTED, EventStatus.CANCELLED}


def series_of(event: Event) -> Event:
    """Reminders belong to the series; a changed occurrence is reminded of like the others."""
    return event.parent if event.parent_id else event


def reminder_minutes(event: Event, user: User) -> list[int]:
    return sorted(
        EventReminder.objects.filter(event=series_of(event), user=user).values_list("minutes_before", flat=True)
    )


def set_reminders(event: Event, user: User, minutes: list[int]) -> list[int]:
    series = series_of(event)
    wanted = sorted({m for m in minutes if 0 <= m <= MAX_MINUTES_BEFORE})
    with transaction.atomic():
        EventReminder.objects.filter(event=series, user=user).exclude(minutes_before__in=wanted).delete()
        for before in wanted:
            EventReminder.objects.get_or_create(event=series, user=user, minutes_before=before)
        # The user's CalDAV clients show the reminders as alarms and must fetch the event again.
        Event.objects.filter(pk=series.pk).update(updated_at=datetime.now(timezone.utc))
    return wanted


def _local_start(event: Event, start: datetime, user: User) -> datetime:
    # All-day occurrences begin at midnight where the user is, not at midnight UTC.
    if event.all_day:
        local = zone(user.timezone or "UTC")
        return datetime.combine(start.date(), datetime.min.time(), tzinfo=local).astimezone(timezone.utc)
    return start


def _occurrences(series: Event, user: User, after: datetime, before: datetime):
    """(event, start) of the series' occurrences starting in (after, before], changed ones included."""
    found = []
    # All-day starts move by up to a day with the user's zone; look a day further each way.
    for start, _ in expand_event(series, after - timedelta(days=1), before + timedelta(days=1)):
        found.append((series, _local_start(series, start, user)))
    if is_series(series):
        for override in series.overrides.all():
            found.append((override, _local_start(override, make_aware(override.start), user)))
    return [(event, start) for event, start in found if after < start <= before]


def deliver_due_reminders(user: User | None = None, now: datetime | None = None) -> list[dict]:
    """Turns due reminders into notifications; returns those delivered now."""
    now = now or datetime.now(timezone.utc)
    reminders = EventReminder.objects.select_related("event__calendar", "user").filter(
        event__parent__isnull=True, user__is_active=True
    )
    if user is not None:
        reminders = reminders.filter(user=user)
    longest = reminders.aggregate(m=Max("minutes_before"))["m"]
    if longest is None:
        return []
    # Single events can only be due if they start soon; series are checked in full.
    horizon = now + timedelta(minutes=longest) + timedelta(days=1)
    reminders = reminders.exclude(event__rrule__isnull=True, event__rdates=[], event__start__gt=horizon).exclude(
        event__rrule__isnull=True, event__rdates=[], event__end__lt=now - timedelta(days=2)
    )

    if user is None:
        # Deliveries only guard against reminding twice; old ones aren't needed any more.
        ReminderDelivery.objects.filter(occurrence_start__lt=now - timedelta(days=30)).delete()

    delivered = []
    for reminder in reminders:
        series, reader = reminder.event, reminder.user
        membership = get_membership(series.calendar, reader)
        if membership is None:
            continue
        before = timedelta(minutes=reminder.minutes_before)
        # Occurrences whose reminder time has come, and that haven't long begun.
        for event, start in _occurrences(series, reader, now - LATE_DELIVERY, now + before):
            if event.status in _HIDDEN or not can_see_event(event, reader, membership):
                continue
            try:
                with transaction.atomic():
                    ReminderDelivery.objects.create(reminder=reminder, occurrence_start=start)
            except IntegrityError:
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
            delivered.append({"event_id": str(event.id), "title": event.title, **data})
    return delivered
