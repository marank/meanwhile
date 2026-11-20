"""
User groups.
"""

from ninja import Field

from apps.core.schemas.common import Id, Schema, Text


class GroupOut(Schema):
    id: Id
    name: str
    description: str = ""
    member_count: int = 0


class GroupMemberOut(Schema):
    id: Id
    email: str
    display_name: str


class GroupDetailOut(GroupOut):
    members: list[GroupMemberOut] = []


class GroupCreate(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Text = ""
    member_ids: list[Id] = []


class GroupUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: Text = ""
    # Replaces the member list when given.
    member_ids: list[Id] | None = None
