"""
Model signal handlers.
"""

from datetime import datetime, timedelta, timezone

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import Calendar, DeletedEvent, Event

# CalDAV clients that haven't synced for longer than this start over with a full sync.
DELETED_EVENT_RETENTION = timedelta(days=90)


def _touch_series(event: Event) -> None:
    # A changed occurrence is part of its series' iCalendar object, so the series counts as changed.
    Event.objects.filter(pk=event.parent_id).update(updated_at=datetime.now(timezone.utc))


@receiver(post_save, sender=Event)
def touch_series_of_saved_occurrence(sender, instance: Event, **kwargs) -> None:
    if instance.parent_id:
        _touch_series(instance)


@receiver(post_delete, sender=Event)
def remember_deleted_event(sender, instance: Event, **kwargs) -> None:
    if instance.parent_id:
        _touch_series(instance)
        return
    DeletedEvent.objects.create(
        calendar_id=instance.calendar_id, href=instance.href or f"{instance.uid}.ics"
    )
    DeletedEvent.objects.filter(
        deleted_at__lt=datetime.now(timezone.utc) - DELETED_EVENT_RETENTION
    ).delete()


@receiver(post_delete, sender=Calendar)
def forget_deleted_events_of_calendar(sender, instance: Calendar, **kwargs) -> None:
    DeletedEvent.objects.filter(calendar_id=instance.id).delete()
