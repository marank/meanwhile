"""
User group endpoints.
"""

from typing import Any

from django.db.models import Count, QuerySet
from ninja import Router

from core.models import User, UserGroup
from core.models.base import AnyId
from core.schemas import GroupCreate, GroupDetailOut, GroupMemberOut, GroupOut, GroupUpdate, OkOut
from core.views.common import AuthedRequest, require_admin

router = Router()


@router.get("/groups", response=list[GroupOut])
def list_groups(request: AuthedRequest) -> QuerySet[UserGroup]:
    groups = UserGroup.objects.annotate(member_count=Count("user_set")).order_by("name")
    return groups


def _set_members(group: UserGroup, member_ids: list[str]) -> None:
    group.user_set.set(User.objects.filter(id__in=member_ids))


def _with_member_count(group_id: AnyId) -> UserGroup:
    return UserGroup.objects.annotate(member_count=Count("user_set")).get(id=group_id)


@router.post("/groups", response=GroupOut)
def create_group(request: AuthedRequest, payload: GroupCreate) -> UserGroup:
    require_admin(request)
    group = UserGroup.objects.create(name=payload.name, description=payload.description)
    _set_members(group, payload.member_ids)
    return _with_member_count(group.id)


def _group_detail(group_id: AnyId) -> dict[str, Any]:
    group = _with_member_count(group_id)
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "member_count": group.member_count,  # type: ignore[attr-defined]  # annotated by _with_member_count
        "members": [GroupMemberOut.model_validate(u) for u in group.user_set.all()],
    }


@router.get("/groups/{group_id}", response=GroupDetailOut)
def get_group(request: AuthedRequest, group_id: str) -> dict[str, Any]:
    return _group_detail(group_id)


@router.patch("/groups/{group_id}", response=GroupOut)
def update_group(request: AuthedRequest, group_id: str, payload: GroupUpdate) -> UserGroup:
    require_admin(request)
    group = UserGroup.objects.get(id=group_id)
    data = payload.dict(exclude_unset=True)
    member_ids = data.pop("member_ids", None)
    for attr, value in data.items():
        setattr(group, attr, value)
    group.save()
    if member_ids is not None:
        _set_members(group, member_ids)
    return _with_member_count(group.id)


@router.delete("/groups/{group_id}", response=OkOut)
def delete_group(request: AuthedRequest, group_id: str) -> dict[str, bool]:
    require_admin(request)
    UserGroup.objects.filter(id=group_id).delete()
    return {"ok": True}


@router.post("/groups/{group_id}/members/{user_id}", response=GroupDetailOut)
def add_member(request: AuthedRequest, group_id: str, user_id: str) -> dict[str, Any]:
    require_admin(request)
    group = UserGroup.objects.get(id=group_id)
    user = User.objects.get(id=user_id)
    group.user_set.add(user)
    return _group_detail(group_id)


@router.delete("/groups/{group_id}/members/{user_id}", response=GroupDetailOut)
def remove_member(request: AuthedRequest, group_id: str, user_id: str) -> dict[str, Any]:
    require_admin(request)
    group = UserGroup.objects.get(id=group_id)
    user = User.objects.get(id=user_id)
    group.user_set.remove(user)
    return _group_detail(group_id)
