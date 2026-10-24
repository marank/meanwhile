"""
Calendar and membership models.
"""

from django.db import models

from core.models.base import MembershipSource, Role, TimestampedModel, UUIDModel
from core.models.calendar_colors import DEFAULT_COLORS
from core.models.users import User, UserGroup


def _color_field(name: str):
    return models.CharField(max_length=7, default=DEFAULT_COLORS[name])


class CalendarAppearance(models.Model):
    """Week layout and colors, shared by calendars and the calendar overview."""

    # The week layout: empty follows the app's defaults (AppSettings), also when they change later;
    # set once someone chooses a value. The API fills in the defaults (schemas.WeekLayoutOut).
    first_weekday = models.IntegerField(blank=True, null=True, default=None)
    show_weekends = models.BooleanField(blank=True, null=True, default=None)
    weekend_days = models.JSONField(blank=True, null=True, default=None)
    show_week_numbers = models.BooleanField(blank=True, null=True, default=None)
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

    LAYOUT_FIELDS = ("first_weekday", "show_weekends", "weekend_days", "show_week_numbers")

    class Meta:
        abstract = True


class Calendar(UUIDModel, TimestampedModel, CalendarAppearance):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    force_all_day = models.BooleanField(default=False)
    # Path name a CalDAV client chose when it created the calendar; the id serves as path otherwise.
    dav_name = models.CharField(max_length=255, unique=True, blank=True, null=True)
    url_path = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_public = models.BooleanField(default=False)
    public_role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.READ
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="calendars_owned"
    )

    class Meta:
        db_table = "calendars"

    def __str__(self) -> str:
        return self.name


class CalendarMember(UUIDModel):
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="memberships"
    )
    source = models.CharField(max_length=10, choices=MembershipSource.choices, default=MembershipSource.DIRECT)
    # Granted with a direct membership only. From a group or a public calendar the role is what they give, worked
    # out when it's needed (core.services.permissions.get_membership), so there is none to keep in step.
    role = models.CharField(  # noqa: DJ001
        max_length=20, choices=Role.choices, default=Role.READ, null=True, blank=True
    )
    # Where the calendar sits in the user's sidebar.
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


class CalendarGroup(UUIDModel, TimestampedModel):
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="calendar_groups"
    )
    group = models.ForeignKey(
        UserGroup, on_delete=models.CASCADE, related_name="calendar_groups"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.READ)

    class Meta:
        db_table = "calendar_groups"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "group"], name="uq_calendar_group"
            )
        ]


class CalendarApprover(UUIDModel):
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


class FeedToken(UUIDModel):
    """A user's own iCal feed URL of a calendar; it works while they have access to the calendar."""

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name="feed_tokens")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    token = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = "feed_tokens"
        constraints = [
            models.UniqueConstraint(fields=["calendar", "user"], name="uq_feed_token")
        ]


class OverviewSettings(CalendarAppearance):
    """A user's settings for the views that combine calendars: "All calendars" and folders."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name="overview_settings")
    # Show each event in its calendar's event color instead of the overview's own.
    use_calendar_colors = models.BooleanField(default=True)

    class Meta:
        db_table = "overview_settings"
