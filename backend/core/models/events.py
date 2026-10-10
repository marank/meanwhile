"""
Event, comment, activity, and notification models.
"""

from django.db import models

from core.models.base import EventStatus, new_uuid7, ParticipantStatus
from core.models.calendars import Calendar
from core.models.resources import Resource
from core.models.users import User


class Event(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="events"
    )
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_events"
    )
    title = models.CharField(max_length=255, default="", blank=True)
    description = models.TextField(blank=True, null=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    show_recurrence_count = models.BooleanField(default=False)
    rrule = models.TextField(blank=True, null=True)
    uid = models.CharField(max_length=255, db_index=True)
    raw_ical = models.TextField(blank=True, null=True)
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
    status = models.CharField(
        max_length=20, choices=EventStatus.CHOICES, default=EventStatus.CONFIRMED
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    decided_at = models.DateTimeField(blank=True, null=True)
    decision_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "events"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "uid"], name="uq_event_calendar_uid"
            )
        ]

    @property
    def creator_name(self) -> str | None:
        return self.creator.display_name if self.creator else None

    @property
    def creator_email(self) -> str | None:
        return self.creator.email if self.creator else None

    def __str__(self) -> str:
        return self.title or "Untitled event"


class EventParticipant(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="participants"
    )
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
        choices=ParticipantStatus.CHOICES,
        default=ParticipantStatus.NEEDS_ACTION,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "event_participants"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"], name="uq_event_participant_user"
            ),
            models.UniqueConstraint(
                fields=["event", "email"], name="uq_event_participant_email"
            ),
        ]


class EventComment(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="+"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_comments"


class EventActivity(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="activity"
    )
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


class Notification(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
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
