from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Folder, User
from app.schemas import FolderCreate, FolderOut, FolderUpdate

router = APIRouter(prefix="/users/me/folders", tags=["folders"])


def _is_descendant(db: Session, parent: Folder, candidate_id: str) -> bool:
    if candidate_id is None:
        return False
    current = parent
    while current.parent_id is not None:
        if current.parent_id == candidate_id:
            return True
        current = db.query(Folder).filter(Folder.id == current.parent_id).first()
        if current is None:
            return False
    return False


@router.get("", response_model=List[FolderOut])
def list_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Folder]:
    return (
        db.query(Folder)
        .filter(Folder.user_id == current_user.id)
        .order_by(Folder.position.asc(), Folder.name.asc())
        .all()
    )


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    data: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Folder:
    if data.parent_id:
        parent = (
            db.query(Folder)
            .filter(Folder.id == data.parent_id, Folder.user_id == current_user.id)
            .first()
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found",
            )
    folder = Folder(
        user_id=current_user.id,
        name=data.name,
        parent_id=data.parent_id,
        position=data.position,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: str,
    data: FolderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Folder:
    folder = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.user_id == current_user.id)
        .first()
    )
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    if data.parent_id is not None:
        new_parent_id = data.parent_id if data.parent_id else None
        if new_parent_id == folder_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A folder cannot be its own parent",
            )
        if new_parent_id is not None:
            parent = (
                db.query(Folder)
                .filter(Folder.id == new_parent_id, Folder.user_id == current_user.id)
                .first()
            )
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent folder not found",
                )
            if _is_descendant(folder, new_parent_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create a folder cycle",
                )
        folder.parent_id = new_parent_id

    if data.name is not None:
        folder.name = data.name
    if data.position is not None:
        folder.position = data.position

    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    folder = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.user_id == current_user.id)
        .first()
    )
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )
    parent_id: Optional[str] = folder.parent_id
    db.query(Folder).filter(Folder.parent_id == folder_id).update(
        {"parent_id": parent_id}, synchronize_session=False
    )
    db.query(CalendarMember).filter(CalendarMember.folder_id == folder_id).update(
        {"folder_id": parent_id}, synchronize_session=False
    )
    db.delete(folder)
    db.commit()
