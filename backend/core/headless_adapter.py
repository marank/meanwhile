"""
Custom django-allauth headless adapter.

Answers login and signup with the user as /api/users/me shows them (ProfileOut), so the SPA reads
both alike and the payload follows the API schema.
"""

from typing import Any

from allauth.headless.adapter import DefaultHeadlessAdapter

from core.models import User
from core.schemas import ProfileOut


class HeadlessAdapter(DefaultHeadlessAdapter):  # type: ignore[misc]  # allauth ships no types
    def serialize_user(self, user: User) -> dict[str, Any]:
        # Not in JSON mode: allauth encodes it like Ninja does (DjangoJSONEncoder), times included.
        return ProfileOut.from_orm(user).model_dump()
