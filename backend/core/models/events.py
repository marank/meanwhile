"""
Event, comment, activity, and notification models.
"""

import secrets

from django.db import models
from django.utils import timezone

from core.models.base import EventStatus, ParticipantStatus, TimestampedModel, UUIDModel
from core.models.calendars import Calendar
from core.models.resources import Resource
from core.models.users import User


class Event(UUIDModel, TimestampedModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name="events")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_events")
    title = models.CharField(max_length=255, default="", blank=True)
    description = models.TextField(blank=True, default="")
    # Where the event takes place, as free text (an address, a link, ...). When a location resource
    # is booked, it is that resource's name.
    location = models.CharField(max_length=255, default="", blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    # IANA name of the zone the event was planned in. Recurrences of timed events repeat at the same
    # local time and on the same local weekday in this zone; all-day events don't depend on it.
    timezone = models.CharField(max_length=64, default="UTC")
    show_recurrence_count = models.BooleanField(default=False)
    # NULL: the event doesn't repeat by a rule (it may still have rdates).
    rrule = models.TextField(blank=True, null=True)  # noqa: DJ001
    # Starts (UTC, ISO 8601) of occurrences removed from the series.
    exdates = models.JSONField(default=list, blank=True)
    # Starts (UTC, ISO 8601) of occurrences added to the series besides those of its rrule (RDATE).
    rdates = models.JSONField(default=list, blank=True)
    # An event with a parent replaces one occurrence of that series: the one starting at recurrence_id.
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="overrides", blank=True, null=True)
    recurrence_id = models.DateTimeField(blank=True, null=True)
    uid = models.CharField(max_length=255, db_index=True)
    # Name a CalDAV client stored the event under; clients may pick it freely. Empty means "{uid}.ics" (dav_href).
    # NULL rather than "", which would collide in uq_event_calendar_href.
    href = models.CharField(max_length=255, blank=True, null=True)  # noqa: DJ001
    raw_ical = models.TextField(blank=True, default="")
    category = models.ForeignKey(
        "Category",
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    # The place booked as the event's location (a resource marked as location); besides `resource`.
    location_resource = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        related_name="location_events",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.CONFIRMED)
    # Ids of the booked resources whose approval a pending event still waits for.
    awaiting_approval = models.JSONField(default=list, blank=True)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    decided_at = models.DateTimeField(blank=True, null=True)
    decision_note = models.TextField(blank=True, default="")
    # iCalendar SEQUENCE: counts the changes participants were sent (iMIP), so their mail
    # programs replace older invitations.
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "events"
        constraints = [
            # Changed occurrences share the UID of their series.
            models.UniqueConstraint(
                fields=["calendar", "uid"],
                condition=models.Q(parent__isnull=True),
                name="uq_event_calendar_uid",
            ),
            models.UniqueConstraint(fields=["calendar", "href"], name="uq_event_calendar_href"),
            models.UniqueConstraint(fields=["parent", "recurrence_id"], name="uq_event_parent_recurrence_id"),
        ]

    def __str__(self) -> str:
        return self.title or "Untitled event"

    @property
    def dav_href(self) -> str:
        """The event's name in its CalDAV collection."""
        return self.href or f"{self.uid}.ics"

    @property
    def creator_name(self) -> str | None:
        return self.creator.display_name if self.creator else None

    @property
    def creator_email(self) -> str | None:
        return self.creator.email if self.creator else None


class DeletedEvent(models.Model):
    """Where a deleted event was, so CalDAV clients learn about the deletion when they sync."""

    # No foreign key: the record of an event outlives it, and a deleted calendar takes its records along.
    calendar_id = models.UUIDField(db_index=True)
    href = models.CharField(max_length=255)
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "deleted_events"


class EventReminder(UUIDModel):
    """A reminder of one user before every occurrence of an event (of a series: of all of them)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reminders")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    minutes_before = models.PositiveIntegerField()
    # When the reminder is next due (its next occurrence's start less minutes_before); None when no
    # occurrence is left. "Now" has it worked out (again) by the next delivery (core.services.reminders).
    next_due_at = models.DateTimeField(default=timezone.now, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_reminders"
        constraints = [models.UniqueConstraint(fields=["event", "user", "minutes_before"], name="uq_event_reminder")]


class ReminderDelivery(models.Model):
    """A reminder that went out for one occurrence, so it goes out only once."""

    reminder = models.ForeignKey(EventReminder, on_delete=models.CASCADE, related_name="deliveries")
    occurrence_start = models.DateTimeField()
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reminder_deliveries"
        constraints = [models.UniqueConstraint(fields=["reminder", "occurrence_start"], name="uq_reminder_delivery")]


def new_rsvp_token() -> str:
    return secrets.token_urlsafe(32)


class EventParticipant(UUIDModel, TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="event_participations",
        blank=True,
        null=True,
    )
    email = models.EmailField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.NEEDS_ACTION,
    )
    # Lets the participant answer from the link in their invitation email, without an account.
    rsvp_token = models.CharField(max_length=64, unique=True, default=new_rsvp_token, editable=False)

    class Meta:
        db_table = "event_participants"
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="uq_event_participant_user"),
            models.UniqueConstraint(fields=["event", "email"], name="uq_event_participant_email"),
        ]


class EventEmailMute(UUIDModel):
    """A user who wants no more emails about an event (a series as a whole), from the link in an email's
    footer. The app still shows its notifications."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_email_mutes"
        constraints = [models.UniqueConstraint(fields=["user", "event"], name="uq_event_email_mute")]


class EventComment(UUIDModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_comments"


class EventActivity(UUIDModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=32)
    details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_activity"
        verbose_name_plural = "Event activities"


class Notification(UUIDModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=40)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="+",
        blank=True,
        null=True,
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=255)
    data = models.JSONField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
