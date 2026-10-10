"""
Sidebar folder model.
"""

from django.db import models

from core.models.base import new_uuid7
from core.models.users import User


class Folder(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        blank=True,
        null=True,
    )
    position = models.IntegerField(default=0)

    class Meta:
        db_table = "folders"

    def __str__(self) -> str:
        return self.name
