"""
User group endpoints.
"""

from django.db.models import Count
from ninja.security import django_auth

from core.api import CSRFRouter
from core.models import User, UserGroup
from core.schemas import GroupCreate, GroupDetailOut, GroupMemberOut, GroupOut, GroupUpdate
from core.views.common import require_admin

router = CSRFRouter()


@router.get("/groups", response=list[GroupOut], auth=django_auth)
def list_groups(request):
    groups = UserGroup.objects.annotate(member_count=Count("user_set")).order_by("name")
    return groups


def _set_members(group: UserGroup, member_ids: list[str]):
    group.user_set.set(User.objects.filter(id__in=member_ids))


def _with_member_count(group_id) -> UserGroup:
    return UserGroup.objects.annotate(member_count=Count("user_set")).get(id=group_id)


@router.post("/groups", response=GroupOut, auth=django_auth)
def create_group(request, payload: GroupCreate):
    require_admin(request)
    group = UserGroup.objects.create(name=payload.name, description=payload.description)
    _set_members(group, payload.member_ids)
    return _with_member_count(group.id)


@router.get("/groups/{group_id}", response=GroupDetailOut, auth=django_auth)
def get_group(request, group_id: str):
    group = _with_member_count(group_id)
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "member_count": group.member_count,
        "members": [
            GroupMemberOut.model_validate(u) for u in group.user_set.all()
        ],
    }


@router.patch("/groups/{group_id}", response=GroupOut, auth=django_auth)
def update_group(request, group_id: str, payload: GroupUpdate):
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


@router.delete("/groups/{group_id}", auth=django_auth)
def delete_group(request, group_id: str):
    require_admin(request)
    UserGroup.objects.filter(id=group_id).delete()
    return {"ok": True}


@router.post("/groups/{group_id}/members/{user_id}", response=GroupDetailOut, auth=django_auth)
def add_member(request, group_id: str, user_id: str):
    require_admin(request)
    group = UserGroup.objects.get(id=group_id)
    user = User.objects.get(id=user_id)
    group.user_set.add(user)
    return get_group(request, group_id)


@router.delete("/groups/{group_id}/members/{user_id}", response=GroupDetailOut, auth=django_auth)
def remove_member(request, group_id: str, user_id: str):
    require_admin(request)
    group = UserGroup.objects.get(id=group_id)
    user = User.objects.get(id=user_id)
    group.user_set.remove(user)
    return get_group(request, group_id)
