"""
Search results.
"""

from core.schemas.common import Id, Schema


class SearchResult(Schema):
    id: Id
    type: str
    label: str
    subtitle: str | None = None
    meta: dict | None = None
