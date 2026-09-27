import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import get_db
from app.deps import CurrentAdmin
from app.models import User, get_or_create_app_settings
from app.schemas import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AppSettingsOut,
    AppSettingsUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=AppSettingsOut)
def get_app_settings(
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> "AppSettings":
    return get_or_create_app_settings(db)


@router.patch("/settings", response_model=AppSettingsOut)
def update_app_settings(
    data: AppSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> "AppSettings":
    settings = get_or_create_app_settings(db)
    if data.app_name is not None:
        settings.app_name = data.app_name
    if data.logo_url is not None:
        settings.logo_url = data.logo_url
    if data.favicon_url is not None:
        settings.favicon_url = data.favicon_url
    if data.default_first_weekday is not None:
        settings.default_first_weekday = data.default_first_weekday
    if data.default_show_weekends is not None:
        settings.default_show_weekends = data.default_show_weekends
    if data.default_weekend_days is not None:
        settings.default_weekend_days = sorted(set(data.default_weekend_days))
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/users", response_model=List[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> List[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=data.email,
        display_name=data.display_name,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
        is_active=data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if data.email is not None:
        existing = db.query(User).filter(User.email == data.email, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user.email = data.email
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    if user.id == current_user.id and (
        data.is_admin is False or data.is_active is False
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote or deactivate your own account",
        )
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = CurrentAdmin,
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    password = secrets.token_urlsafe(16)
    user.hashed_password = hash_password(password)
    db.commit()
    return {"password": password}
