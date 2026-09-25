from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Calendar, Resource, ResourceApprover, User
from app.schemas import (
    ApproverCreate,
    ApproverOut,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from app.services.permissions import (
    get_membership,
    is_owner,
    require_membership,
)

router = APIRouter(prefix="", tags=["resources"])


def _serialize_resource(resource: Resource) -> ResourceOut:
    return ResourceOut(
        id=resource.id,
        calendar_id=resource.calendar_id,
        name=resource.name,
        description=resource.description,
        color=resource.color,
        requires_approval=resource.requires_approval,
        is_active=resource.is_active,
        approvers=[
            ApproverOut(
                user_id=approver.user_id,
                email=approver.user.email,
                display_name=approver.user.display_name,
            )
            for approver in resource.approvers
        ],
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


@router.get("/calendars/{calendar_id}/resources", response_model=List[ResourceOut])
def list_resources(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ResourceOut]:
    require_membership(db, calendar_id, current_user.id)
    resources = (
        db.query(Resource)
        .filter(Resource.calendar_id == calendar_id)
        .order_by(Resource.name.asc())
        .all()
    )
    return [_serialize_resource(r) for r in resources]


@router.post("/calendars/{calendar_id}/resources", response_model=ResourceOut, status_code=201)
def create_resource(
    calendar_id: str,
    data: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceOut:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can create resources",
        )
    resource = Resource(
        calendar_id=calendar_id,
        name=data.name,
        description=data.description,
        color=data.color,
        requires_approval=data.requires_approval,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return _serialize_resource(resource)


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceOut:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    require_membership(db, resource.calendar_id, current_user.id)
    return _serialize_resource(resource)


@router.patch("/{resource_id}", response_model=ResourceOut)
def update_resource(
    resource_id: str,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceOut:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    membership = require_membership(db, resource.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update resources",
        )
    if data.name is not None:
        resource.name = data.name
    if "description" in data.model_fields_set:
        resource.description = data.description
    if data.color is not None:
        resource.color = data.color
    if data.requires_approval is not None:
        resource.requires_approval = data.requires_approval
    if data.is_active is not None:
        resource.is_active = data.is_active
    db.commit()
    db.refresh(resource)
    return _serialize_resource(resource)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    membership = require_membership(db, resource.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete resources",
        )
    db.delete(resource)
    db.commit()


@router.get("/{resource_id}/approvers", response_model=List[ApproverOut])
def list_resource_approvers(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ApproverOut]:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    membership = require_membership(db, resource.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can view resource approvers",
        )
    return [
        ApproverOut(
            user_id=approver.user_id,
            email=approver.user.email,
            display_name=approver.user.display_name,
        )
        for approver in resource.approvers
    ]


@router.post("/{resource_id}/approvers", response_model=ApproverOut, status_code=201)
def add_resource_approver(
    resource_id: str,
    data: ApproverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApproverOut:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    membership = require_membership(db, resource.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can add resource approvers",
        )
    approver_membership = get_membership(db, resource.calendar_id, data.user_id)
    if approver_membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approver must be a calendar member",
        )
    existing = (
        db.query(ResourceApprover)
        .filter_by(resource_id=resource_id, user_id=data.user_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an approver for this resource",
        )
    approver = ResourceApprover(resource_id=resource_id, user_id=data.user_id)
    db.add(approver)
    db.commit()
    db.refresh(approver)
    return ApproverOut(
        user_id=approver.user_id,
        email=approver.user.email,
        display_name=approver.user.display_name,
    )


@router.delete("/{resource_id}/approvers/{user_id}", status_code=204)
def remove_resource_approver(
    resource_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    membership = require_membership(db, resource.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can remove resource approvers",
        )
    approver = (
        db.query(ResourceApprover)
        .filter_by(resource_id=resource_id, user_id=user_id)
        .first()
    )
    if approver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approver not found",
        )
    db.delete(approver)
    db.commit()
