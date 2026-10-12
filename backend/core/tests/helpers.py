"""
Helpers for tests driven through the HTTP API.
"""

import json
from datetime import UTC, datetime

from django.test import Client

from core.models import User

BASE = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)  # a Monday


def iso(dt: datetime) -> str:
    return dt.isoformat()


class Api:
    """Session-authenticated JSON client for one user."""

    def __init__(self, user: User):
        self.client = Client()
        self.client.force_login(user)
        self.user = user

    def _call(self, method: str, url: str, data=None):
        kwargs = {"content_type": "application/json"}
        if data is not None:
            kwargs["data"] = json.dumps(data)
        return getattr(self.client, method)(f"/api{url}", **kwargs)

    def get(self, url):
        return self._call("get", url)

    def post(self, url, data=None):
        return self._call("post", url, data if data is not None else {})

    def patch(self, url, data):
        return self._call("patch", url, data)

    def put(self, url, data):
        return self._call("put", url, data)

    def delete(self, url):
        return self._call("delete", url)


def make_user(name: str) -> User:
    return User.objects.create_user(email=f"{name}@example.test", password="x", display_name=name.title())


def add_approver(world, path: str, name: str):
    """Adds a user to the approvers at `path`, keeping the others (the API sets the whole list)."""
    owner = world["api"]["owner"]
    current = [a["user_id"] for a in owner.get(path).json()]
    return owner.put(path, {"user_ids": [*current, str(world["users"][name].id)]})


def add_default_approver(world, name: str):
    res = add_approver(world, f"/calendars/{world['cal']['id']}/approvers", name)
    assert res.status_code == 200, res.content
