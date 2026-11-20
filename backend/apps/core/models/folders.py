"""
Sidebar folder model.
"""

from django.db import models

from apps.core.models.base import UUIDModel
from apps.core.models.users import User


class Folder(UUIDModel):
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
