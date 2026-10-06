from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import SearchResult
from app.services.permissions import require_membership
from app.services.search import (
    search_categories,
    search_groups,
    search_resources,
    search_users,
)

router = APIRouter(tags=["search"])


@router.get("/search", response_model=List[SearchResult])
def search(
    entity: str,
    q: str = "",
    limit: int = Query(20, ge=1, le=100),
    calendar_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SearchResult]:
    if entity == "users":
        return search_users(db, q, limit)
    if entity == "groups":
        return search_groups(db, q, limit)
    if entity in {"resources", "categories"}:
        if calendar_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="calendar_id is required for this entity",
            )
        require_membership(db, calendar_id, current_user.id)
        if entity == "resources":
            return search_resources(db, calendar_id, q, limit)
        return search_categories(db, calendar_id, q, limit)
    raise HTTPException(status_code=400, detail="Unknown search entity")
