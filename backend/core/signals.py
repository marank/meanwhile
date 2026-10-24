"""
Model signal handlers.
"""

from datetime import timedelta
from uuid import UUID

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import (
    Calendar,
    CalendarGroup,
    CalendarMember,
    DeletedEvent,
    Event,
    EventParticipant,
    Folder,
    Notification,
    User,
    UserGroup,
)
from core.realtime import broadcast
from core.services import memberships, reminders

# CalDAV clients that haven't synced for longer than this start over with a full sync.
DELETED_EVENT_RETENTION = timedelta(days=90)


def _deleted_along(origin, model) -> bool:
    """Whether a deletion started at an object (or a queryset) of `model`."""
    return isinstance(origin, model) or getattr(origin, "model", None) is model


def _touch_series(series_id: UUID) -> None:
    # A changed occurrence is part of its series' iCalendar object, so the series counts as changed.
    Event.objects.filter(pk=series_id).update(updated_at=timezone.now())


@receiver(post_save, sender=Event)
def touch_series_of_saved_occurrence(sender, instance: Event, **kwargs) -> None:
    if instance.parent_id:
        _touch_series(instance.parent_id)


@receiver(post_delete, sender=Event)
def remember_deleted_event(sender, instance: Event, origin=None, **kwargs) -> None:
    if _deleted_along(origin, Calendar):
        return  # the calendar's record of deleted events goes with it
    if instance.parent_id:
        if not (isinstance(origin, Event) and origin.pk == instance.parent_id):
            _touch_series(instance.parent_id)  # not when the whole series goes
        return
    # Old records are removed regularly (core.tasks).
    DeletedEvent.objects.create(calendar_id=instance.calendar_id, href=instance.dav_href)


@receiver(post_save, sender=Event)
@receiver(post_delete, sender=Event)
def work_out_reminders_again(sender, instance: Event, raw: bool = False, origin=None, **kwargs) -> None:
    # A new time, rule or status, or a changed occurrence, moves when the series' reminders are due.
    if raw or _deleted_along(origin, Calendar) or (instance.parent_id is None and _deleted_along(origin, Event)):
        return  # their reminders go too
    reminders.reminders_changed(series_id=instance.parent_id or instance.pk)


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
    """Everyone whose list of calendars shows the calendar: its members (granted, from a group or added) and
    the members of linked groups."""
    users = set(CalendarMember.objects.filter(calendar_id=calendar_id).values_list("user_id", flat=True))
    users |= set(User.objects.filter(groups__calendar_groups__calendar_id=calendar_id).values_list("pk", flat=True))
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


# Memberships from a group or a public calendar follow what they come from (core.services.memberships).
# Fixtures (loaddata, `raw`) bring their memberships along, so their rows aren't synced.


@receiver(post_save, sender=Calendar)
def sync_public_memberships(sender, instance: Calendar, raw: bool = False, **kwargs) -> None:
    if not raw:
        memberships.sync_public(instance)


@receiver(post_save, sender=CalendarGroup)
@receiver(post_delete, sender=CalendarGroup)
def sync_group_link_memberships(sender, instance: CalendarGroup, raw: bool = False, **kwargs) -> None:
    if raw:
        return
    # Going with its calendar, the link takes nothing along that would have to be replaced.
    if _deleted_along(kwargs.get("origin"), Calendar):
        return
    memberships.sync_group_link(instance.calendar_id)


@receiver(m2m_changed, sender=User.groups.through)
def sync_group_memberships(sender, instance, action, reverse, pk_set, **kwargs) -> None:
    if reverse:
        _group_members_changed(instance, action, pk_set)
    else:
        _user_groups_changed(instance, action, pk_set)


def _user_groups_changed(user: User, action: str, group_ids: set | None) -> None:
    """user.groups.add/remove/clear: the calendars of these groups (of all, when cleared) may come or go."""
    if action in {"post_add", "post_remove"}:
        memberships.sync_user_groups(user.pk, group_ids)
    elif action == "post_clear":
        memberships.sync_user_groups(user.pk)


def _group_members_changed(group: UserGroup, action: str, user_ids: set | None) -> None:
    """group.user_set.add/remove/clear: these users may gain or lose the group's calendars."""
    if action == "pre_clear":
        # Once cleared, the group can't tell who was in it.
        group.__dict__["_cleared_user_ids"] = list(group.user_set.values_list("pk", flat=True))
        return
    if action == "post_clear":
        user_ids = group.__dict__.pop("_cleared_user_ids", [])
    elif action not in {"post_add", "post_remove"} or user_ids is None:
        return  # adding and removing always name the users
    for user_id in user_ids:
        memberships.sync_user_groups(user_id, [group.pk])


@receiver(post_save, sender=Folder)
@receiver(post_delete, sender=Folder)
def announce_folder_change(sender, instance: Folder, **kwargs) -> None:
    broadcast.calendars_changed([instance.user_id])
