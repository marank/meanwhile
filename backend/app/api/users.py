import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import get_db
from app.deps import get_current_user
from app.models import AppPassword, User
from app.schemas import (
    AppPasswordCreate,
    AppPasswordCreated,
    AppPasswordOut,
    UserOut,
    UserSearchResult,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserOut)
def update_current_user(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if data.display_name:
        current_user.display_name = data.display_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/search", response_model=List[UserSearchResult])
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[User]:
    if len(q) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must be at least 2 characters",
        )
    users = (
        db.query(User)
        .filter(
            or_(
                User.email.ilike(f"%{q}%"),
                User.display_name.ilike(f"%{q}%"),
            )
        )
        .limit(20)
        .all()
    )
    return users


@router.get("/me/app-passwords", response_model=List[AppPasswordOut])
def list_app_passwords(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AppPassword]:
    return (
        db.query(AppPassword)
        .filter(AppPassword.user_id == current_user.id)
        .order_by(AppPassword.created_at.desc())
        .all()
    )


@router.post("/me/app-passwords", response_model=AppPasswordCreated)
def create_app_password(
    data: AppPasswordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppPasswordCreated:
    plaintext = secrets.token_urlsafe(32)
    app_password = AppPassword(
        user_id=current_user.id,
        label=data.label,
        password_hash=hash_password(plaintext),
    )
    db.add(app_password)
    db.commit()
    db.refresh(app_password)
    return AppPasswordCreated(
        id=app_password.id,
        label=app_password.label,
        password=plaintext,
    )


@router.delete("/me/app-passwords/{app_password_id}")
def delete_app_password(
    app_password_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    app_password = (
        db.query(AppPassword)
        .filter(
            AppPassword.id == app_password_id,
            AppPassword.user_id == current_user.id,
        )
        .first()
    )
    if not app_password:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App password not found",
        )
    db.delete(app_password)
    db.commit()
    return {"ok": True}
