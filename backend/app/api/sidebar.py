from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CalendarMember, Folder, User

router = APIRouter(prefix="/sidebar", tags=["sidebar"])


class SidebarReorderItem(BaseModel):
    type: Literal["folder", "calendar"]
    id: str
    parent_id: Optional[str] = None
    position: int


class SidebarReorderRequest(BaseModel):
    items: List[SidebarReorderItem]


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_sidebar(
    data: SidebarReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    folder_items = [item for item in data.items if item.type == "folder"]
    calendar_items = [item for item in data.items if item.type == "calendar"]

    folder_ids = {item.id for item in folder_items}
    calendar_ids = {item.id for item in calendar_items}

    folders = {
        f.id: f
        for f in db.query(Folder)
        .filter(Folder.user_id == current_user.id, Folder.id.in_(folder_ids))
        .all()
    }
    if len(folders) != len(folder_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more folders not found",
        )

    memberships = {
        m.calendar_id: m
        for m in db.query(CalendarMember)
        .filter(
            CalendarMember.user_id == current_user.id,
            CalendarMember.calendar_id.in_(calendar_ids),
        )
        .all()
    }
    if len(memberships) != len(calendar_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more calendar memberships not found",
        )

    parent_folder_ids = {
        item.parent_id
        for item in data.items
        if item.parent_id is not None
    }
    existing_parents = {
        f.id
        for f in db.query(Folder)
        .filter(Folder.user_id == current_user.id, Folder.id.in_(parent_folder_ids))
        .all()
    }
    for item in data.items:
        if item.parent_id and item.parent_id not in existing_parents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found",
            )

    # Self-parent check and cycle detection using the final parent map.
    all_folders = db.query(Folder).filter(Folder.user_id == current_user.id).all()
    parent_map = {f.id: f.parent_id for f in all_folders}
    for item in folder_items:
        if item.parent_id == item.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A folder cannot be its own parent",
            )
        parent_map[item.id] = item.parent_id or None

    def has_cycle(folder_id: str) -> bool:
        visited = set()
        current: Optional[str] = folder_id
        while current is not None:
            if current in visited:
                return True
            visited.add(current)
            current = parent_map.get(current)
        return False

    for folder_id in parent_map:
        if has_cycle(folder_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create a folder cycle",
            )

    for item in folder_items:
        folder = folders[item.id]
        folder.parent_id = item.parent_id or None
        folder.position = item.position

    for item in calendar_items:
        membership = memberships[item.id]
        membership.folder_id = item.parent_id or None
        membership.position = item.position

    db.commit()
