from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Category, Resource, User, UserGroup
from app.schemas import SearchResult


def _escaped_query(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_users(db: Session, q: str, limit: int) -> List[SearchResult]:
    q = q.strip()
    if len(q) < 2:
        return []
    pattern = f"%{_escaped_query(q)}%"
    users = (
        db.query(User)
        .filter(or_(User.email.ilike(pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\")))
        .order_by(User.display_name.asc(), User.email.asc())
        .limit(limit)
        .all()
    )
    return [
        SearchResult(id=user.id, type="user", label=user.display_name, subtitle=user.email)
        for user in users
    ]


def search_groups(db: Session, q: str, limit: int) -> List[SearchResult]:
    query = db.query(UserGroup)
    if q.strip():
        query = query.filter(UserGroup.name.ilike(f"%{_escaped_query(q.strip())}%", escape="\\"))
    groups = query.order_by(UserGroup.name.asc()).limit(limit).all()
    return [
        SearchResult(id=group.id, type="group", label=group.name, subtitle=group.description)
        for group in groups
    ]


def search_resources(db: Session, calendar_id: str, q: str, limit: int) -> List[SearchResult]:
    query = db.query(Resource).filter(Resource.calendar_id == calendar_id)
    if q.strip():
        query = query.filter(Resource.name.ilike(f"%{_escaped_query(q.strip())}%", escape="\\"))
    resources = query.order_by(Resource.name.asc()).limit(limit).all()
    return [
        SearchResult(
            id=resource.id,
            type="resource",
            label=resource.name,
            subtitle=resource.description,
            meta={"requires_approval": resource.requires_approval, "color": resource.color},
        )
        for resource in resources
    ]


def search_categories(db: Session, calendar_id: str, q: str, limit: int) -> List[SearchResult]:
    query = db.query(Category).filter(Category.calendar_id == calendar_id)
    if q.strip():
        query = query.filter(Category.name.ilike(f"%{_escaped_query(q.strip())}%", escape="\\"))
    categories = query.order_by(Category.name.asc()).limit(limit).all()
    return [
        SearchResult(
            id=category.id,
            type="category",
            label=category.name,
            meta={"color": category.color},
        )
        for category in categories
    ]
