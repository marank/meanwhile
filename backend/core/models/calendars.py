"""
Calendar and membership models.
"""

from django.db import models

from core.models.base import default_weekend_days, new_uuid7, Role
from core.models.users import User, UserGroup


class Calendar(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default="#3b82f6")
    dark_color = models.CharField(max_length=7, default="#60a5fa")
    force_all_day = models.BooleanField(default=False)
    first_weekday = models.IntegerField(default=0)
    show_weekends = models.BooleanField(default=True)
    weekend_days = models.JSONField(default=default_weekend_days)
    show_week_numbers = models.BooleanField(default=False)
    today_color = models.CharField(max_length=7, default="#eff6ff")
    dark_today_color = models.CharField(max_length=7, default="#27272a")
    weekend_color = models.CharField(max_length=7, default="#f9fafb")
    dark_weekend_color = models.CharField(max_length=7, default="#18181b")
    feed_token = models.CharField(max_length=255, unique=True, db_index=True)
    is_public = models.BooleanField(default=False)
    public_role = models.CharField(
        max_length=20, choices=Role.CHOICES, default=Role.VIEWER
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="calendars_owned"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendars"

    def __str__(self) -> str:
        return self.name


class CalendarMember(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.CHOICES, default=Role.VIEWER)
    folder = models.ForeignKey(
        "Folder",
        on_delete=models.SET_NULL,
        related_name="memberships",
        blank=True,
        null=True,
    )
    position = models.IntegerField(default=0)

    class Meta:
        db_table = "calendar_members"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "user"], name="uq_calendar_member"
            )
        ]


class CalendarGroup(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="calendar_groups"
    )
    group = models.ForeignKey(
        UserGroup, on_delete=models.CASCADE, related_name="calendar_groups"
    )
    role = models.CharField(max_length=20, choices=Role.CHOICES, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_groups"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "group"], name="uq_calendar_group"
            )
        ]


class CalendarApprover(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="approvers"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="+"
    )

    class Meta:
        db_table = "calendar_approvers"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "user"], name="uq_calendar_approver"
            )
        ]
