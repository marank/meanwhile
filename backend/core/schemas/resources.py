"""
Resources, their approvers, and categories.
"""

from datetime import datetime
from typing import Annotated

from ninja import Field
from pydantic import model_validator

from core.schemas.common import Color, Id, Schema, Text


class ApproversIn(Schema):
    """The complete list of approvers; whoever is not in it is no approver any more."""

    user_ids: list[Id]


class ApproverOut(Schema):
    user_id: Id
    email: str
    display_name: str


# An icon's name: lower-case words joined by hyphens, or empty for none. Which names exist is up to the client.
ResourceIconName = Annotated[str, Field(max_length=40, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$|^$")]


class ResourceCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    color: Color = "#f59e0b"
    icon: ResourceIconName = ""
    requires_approval: bool = False
    is_location: bool = False
    is_active: bool = True


class ResourceUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    color: Color | None = None
    icon: ResourceIconName | None = None
    requires_approval: bool | None = None
    is_location: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def refuse_nulls(self) -> ResourceUpdate:
        # A field left out keeps its value; null would empty a column that can't be empty.
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"May not be null: {', '.join(nulls)}")
        return self


class ResourceOut(Schema):
    id: Id
    calendar_id: Id
    name: str
    description: str = ""
    color: str
    icon: str
    requires_approval: bool
    is_location: bool
    is_active: bool
    approvers: list[ApproverOut]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_approvers(obj):
        # The related ResourceApprover rows only carry the user, not its email or name.
        return [
            ApproverOut(user_id=a.user_id, email=a.user.email, display_name=a.user.display_name)
            for a in obj.approvers.all()
        ]


class CategoryCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    color: str = "#64748b"


class CategoryUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    color: str | None = None


class CategoryOut(Schema):
    id: Id
    calendar_id: Id
    name: str
    description: str = ""
    color: str
    created_at: datetime
    updated_at: datetime
