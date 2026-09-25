from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Category, User
from app.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.services.permissions import is_owner, require_membership

router = APIRouter(prefix="", tags=["categories"])


@router.get("/calendars/{calendar_id}/categories", response_model=List[CategoryOut])
def list_categories(
    calendar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Category]:
    require_membership(db, calendar_id, current_user.id)
    return (
        db.query(Category)
        .filter(Category.calendar_id == calendar_id)
        .order_by(Category.name.asc())
        .all()
    )


@router.post("/calendars/{calendar_id}/categories", response_model=CategoryOut, status_code=201)
def create_category(
    calendar_id: str,
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Category:
    membership = require_membership(db, calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(status_code=403, detail="Only the owner can create categories")
    existing = db.query(Category).filter(
        Category.calendar_id == calendar_id,
        Category.name == data.name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    category = Category(calendar_id=calendar_id, **data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    membership = require_membership(db, category.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(status_code=403, detail="Only the owner can update categories")
    if data.name is not None:
        duplicate = db.query(Category).filter(
            Category.calendar_id == category.calendar_id,
            Category.name == data.name,
            Category.id != category.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        category.name = data.name
    if "description" in data.model_fields_set:
        category.description = data.description
    if data.color is not None:
        category.color = data.color
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    membership = require_membership(db, category.calendar_id, current_user.id)
    if not is_owner(membership):
        raise HTTPException(status_code=403, detail="Only the owner can delete categories")
    db.delete(category)
    db.commit()
