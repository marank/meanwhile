"""
Model signal handlers.
"""

from datetime import datetime, timedelta, timezone

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.models import (
    Calendar,
    CalendarGroup,
    CalendarMember,
    CalendarSubscription,
    DeletedEvent,
    Event,
    EventParticipant,
    Folder,
    Notification,
    User,
)
from core.realtime import broadcast

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


# Live updates -------------------------------------------------------------------------------


@receiver(post_save, sender=Event)
@receiver(post_delete, sender=Event)
def announce_event_change(sender, instance: Event, **kwargs) -> None:
    broadcast.calendar_changed(instance.calendar_id)


@receiver(post_save, sender=EventParticipant)
@receiver(post_delete, sender=EventParticipant)
def announce_participant_change(sender, instance: EventParticipant, **kwargs) -> None:
    # Participants see events (e.g. pending bookings) that others don't.
    calendar_id = Event.objects.filter(pk=instance.event_id).values_list("calendar_id", flat=True).first()
    broadcast.calendar_changed(calendar_id)


@receiver(post_save, sender=Notification)
@receiver(post_delete, sender=Notification)
def announce_notification_change(sender, instance: Notification, **kwargs) -> None:
    broadcast.notifications_changed(instance.user_id)


def _calendar_audience(calendar_id) -> set:
    """Everyone whose list of calendars shows the calendar: members, members of linked groups, and those
    who added it (a public one) to their sidebar."""
    users = set(CalendarMember.objects.filter(calendar_id=calendar_id).values_list("user_id", flat=True))
    users |= set(CalendarSubscription.objects.filter(calendar_id=calendar_id).values_list("user_id", flat=True))
    users |= set(
        User.objects.filter(groups__calendar_groups__calendar_id=calendar_id).values_list("pk", flat=True)
    )
    owner = Calendar.objects.filter(pk=calendar_id).values_list("owner_id", flat=True).first()
    if owner:
        users.add(owner)
    return users


@receiver(post_save, sender=Calendar)
def announce_calendar_change(sender, instance: Calendar, **kwargs) -> None:
    # Names, colors and settings. A deleted calendar's members hear it through their memberships.
    broadcast.calendars_changed(_calendar_audience(instance.pk))


@receiver(post_save, sender=CalendarMember)
@receiver(post_delete, sender=CalendarMember)
def announce_membership_change(sender, instance: CalendarMember, **kwargs) -> None:
    broadcast.calendars_changed([instance.user_id])


@receiver(post_save, sender=CalendarSubscription)
@receiver(post_delete, sender=CalendarSubscription)
def announce_subscription_change(sender, instance: CalendarSubscription, **kwargs) -> None:
    broadcast.calendars_changed([instance.user_id])


@receiver(post_save, sender=CalendarGroup)
@receiver(post_delete, sender=CalendarGroup)
def announce_group_link_change(sender, instance: CalendarGroup, **kwargs) -> None:
    broadcast.calendars_changed(User.objects.filter(groups=instance.group_id).values_list("pk", flat=True))


@receiver(m2m_changed, sender=User.groups.through)
def announce_group_membership_change(sender, instance, action, reverse, pk_set, **kwargs) -> None:
    # Joining or leaving a group gives or takes the calendars linked to it.
    if action not in {"post_add", "post_remove", "pre_clear"}:
        return
    if not reverse:
        broadcast.calendars_changed([instance.pk])
    elif pk_set:
        broadcast.calendars_changed(pk_set)
    elif action == "pre_clear":
        broadcast.calendars_changed(instance.user_set.values_list("pk", flat=True))


@receiver(post_save, sender=Folder)
@receiver(post_delete, sender=Folder)
def announce_folder_change(sender, instance: Folder, **kwargs) -> None:
    broadcast.calendars_changed([instance.user_id])
