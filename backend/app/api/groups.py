from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import CurrentAdmin, get_current_user
from app.models import User, UserGroup, user_group_members
from app.schemas import GroupCreate, GroupDetailOut, GroupOut, GroupUpdate

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=List[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GroupOut]:
    results = (
        db.query(UserGroup, func.count(user_group_members.c.user_id).label("member_count"))
        .outerjoin(user_group_members, user_group_members.c.group_id == UserGroup.id)
        .group_by(UserGroup.id)
        .order_by(UserGroup.created_at.desc())
        .all()
    )
    out = []
    for group, count in results:
        group.member_count = count
        out.append(GroupOut.model_validate(group))
    return out


@router.post("", response_model=GroupDetailOut, status_code=201)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> UserGroup:
    group = UserGroup(name=data.name, description=data.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def _get_group(db: Session, group_id: str) -> UserGroup:
    group = (
        db.query(UserGroup)
        .options(joinedload(UserGroup.users))
        .filter(UserGroup.id == group_id)
        .first()
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    group.member_count = len(group.users)
    return group


@router.get("/{group_id}", response_model=GroupDetailOut)
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserGroup:
    return _get_group(db, group_id)


@router.patch("/{group_id}", response_model=GroupDetailOut)
def update_group(
    group_id: str,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> UserGroup:
    group = _get_group(db, group_id)
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    db.commit()
    return _get_group(db, group_id)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> None:
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/members/{user_id}", response_model=GroupDetailOut)
def add_group_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> UserGroup:
    group = _get_group(db, group_id)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user in group.users:
        raise HTTPException(status_code=400, detail="User is already a member of this group")
    group.users.append(user)
    db.commit()
    return _get_group(db, group_id)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> None:
    group = _get_group(db, group_id)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user not in group.users:
        raise HTTPException(status_code=404, detail="User is not a member of this group")
    group.users.remove(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
