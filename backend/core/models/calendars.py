"""
Calendar and membership models.
"""

from django.db import models

from core.models.base import default_weekend_days, new_uuid7, Role
from core.models.calendar_colors import DEFAULT_COLORS
from core.models.users import User, UserGroup


def _color_field(name: str):
    return models.CharField(max_length=7, default=DEFAULT_COLORS[name])


class CalendarAppearance(models.Model):
    """Week layout and colors, shared by calendars and the calendar overview."""

    first_weekday = models.IntegerField(default=0)
    show_weekends = models.BooleanField(default=True)
    weekend_days = models.JSONField(default=default_weekend_days)
    show_week_numbers = models.BooleanField(default=False)
    # Colors per role and theme; see calendar_colors.py.
    base_color = _color_field("base_color")
    weekend_color = _color_field("weekend_color")
    today_color = _color_field("today_color")
    event_color = _color_field("event_color")
    border_color = _color_field("border_color")
    outer_border_color = _color_field("outer_border_color")
    dark_base_color = _color_field("dark_base_color")
    dark_weekend_color = _color_field("dark_weekend_color")
    dark_today_color = _color_field("dark_today_color")
    dark_event_color = _color_field("dark_event_color")
    dark_border_color = _color_field("dark_border_color")
    dark_outer_border_color = _color_field("dark_outer_border_color")

    class Meta:
        abstract = True


class Calendar(CalendarAppearance):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    force_all_day = models.BooleanField(default=False)
    feed_token = models.CharField(max_length=255, unique=True, db_index=True)
    # Path name a CalDAV client chose when it created the calendar; the id serves as path otherwise.
    dav_name = models.CharField(max_length=255, unique=True, blank=True, null=True)
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


class OverviewSettings(CalendarAppearance):
    """A user's settings for the views that combine calendars: "All calendars" and folders."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name="overview_settings")
    # Show each event in its calendar's event color instead of the overview's own.
    use_calendar_colors = models.BooleanField(default=True)

    class Meta:
        db_table = "overview_settings"
