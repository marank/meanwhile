"""
Resource and resource-approver models.
"""

from django.db import models

from core.models.base import new_uuid7
from core.models.calendars import Calendar
from core.models.users import User


class Category(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default="#64748b")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "name"], name="uq_category_calendar_name"
            )
        ]

    def __str__(self) -> str:
        return self.name


class Resource(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    calendar = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, related_name="resources"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default="#f59e0b")
    requires_approval = models.BooleanField(default=False)
    # Inactive resources stay manageable but can't be booked; archived ones count as deleted
    # and are kept only so existing bookings still reference them.
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resources"

    def __str__(self) -> str:
        return self.name


class ResourceApprover(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="approvers"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "resource_approvers"
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "user"], name="uq_resource_approver"
            )
        ]
