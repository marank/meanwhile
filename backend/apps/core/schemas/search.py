"""
Search results.
"""

from typing import Any

from apps.core.schemas.common import Id, Schema


class SearchResult(Schema):
    id: Id
    type: str
    label: str
    subtitle: str | None = None
    meta: dict[str, Any] | None = None
