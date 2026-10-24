"""
Custom django-allauth headless adapter.

Answers login and signup with the user as /api/users/me shows them (ProfileOut), so the SPA reads
both alike and the payload follows the API schema.
"""

from allauth.headless.adapter import DefaultHeadlessAdapter

from core.schemas import ProfileOut


class HeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        # Not in JSON mode: allauth encodes it like Ninja does (DjangoJSONEncoder), times included.
        return ProfileOut.from_orm(user).model_dump()
