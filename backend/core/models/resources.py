"""
Resource and resource-approver models.
"""

from django.db import models

from core.models.base import TimestampedModel, UUIDModel
from core.models.calendars import Calendar
from core.models.users import User


class Category(UUIDModel, TimestampedModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#64748b")

    class Meta:
        db_table = "categories"
        constraints = [models.UniqueConstraint(fields=["calendar", "name"], name="uq_category_calendar_name")]

    def __str__(self) -> str:
        return self.name


class Resource(UUIDModel, TimestampedModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name="resources")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#f59e0b")
    # Name of an icon (kebab-case, e.g. "door-open") the client shows before the resource's name.
    icon = models.CharField(max_length=40, blank=True, default="")
    requires_approval = models.BooleanField(default=False)
    # A place (e.g. a room): offered in an event's location field instead of the resource field;
    # picking it there books it, one event at a time like any resource.
    is_location = models.BooleanField(default=False)
    # Inactive resources stay manageable but can't be booked; archived ones count as deleted
    # and are kept only so existing bookings still reference them.
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "resources"

    def __str__(self) -> str:
        return self.name


class ResourceApprover(UUIDModel):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="approvers")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "resource_approvers"
        constraints = [models.UniqueConstraint(fields=["resource", "user"], name="uq_resource_approver")]
