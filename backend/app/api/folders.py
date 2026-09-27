from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CalendarMember, Folder, User
from app.schemas import FolderCreate, FolderOut, FolderUpdate

router = APIRouter(prefix="/folders", tags=["folders"])


def _is_descendant(
    db: Session, user_id: str, ancestor_id: str | None, candidate_id: str | None
) -> bool:
    if candidate_id is None or ancestor_id is None:
        return False
    if candidate_id == ancestor_id:
        return True
    sql = text(
        """
        WITH RECURSIVE descendants(id) AS (
            SELECT id FROM folders WHERE parent_id = :ancestor_id AND user_id = :user_id
            UNION ALL
            SELECT f.id FROM folders f
            JOIN descendants d ON f.parent_id = d.id
            WHERE f.user_id = :user_id
        )
        SELECT 1 FROM descendants WHERE id = :candidate_id LIMIT 1
        """
    )
    result = db.execute(
        sql, {"ancestor_id": ancestor_id, "candidate_id": candidate_id, "user_id": user_id}
    ).first()
    return result is not None


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

    update_data = data.model_dump(exclude_unset=True)

    if "parent_id" in update_data:
        new_parent_id = update_data["parent_id"] or None
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
            if _is_descendant(db, current_user.id, folder.id, new_parent_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create a folder cycle",
                )
        folder.parent_id = new_parent_id

    if "name" in update_data:
        folder.name = update_data["name"]
    if "position" in update_data:
        folder.position = update_data["position"]

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
